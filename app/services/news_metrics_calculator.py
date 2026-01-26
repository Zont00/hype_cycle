from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from collections import defaultdict, Counter
import numpy as np
import re
import logging

from ..models import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class NewsMetricsSnapshot:
    """Snapshot of all calculated News metrics"""
    # Volume metrics
    total_articles: int
    article_velocity: Dict[str, int]  # year-month -> count
    velocity_trend: str  # "increasing", "decreasing", "stable", "peak_reached"
    avg_articles_per_month: float
    peak_month: str
    peak_count: int
    recent_velocity: float  # articles/month in last 3 months

    # Source distribution
    unique_sources: int
    top_sources: List[Tuple[str, int]]  # (source name, count)
    source_concentration_hhi: float  # 0-1, Herfindahl-Hirschman Index

    # Author metrics
    unique_authors: int
    top_authors: List[Tuple[str, int]]  # (author, count)
    articles_without_author_percentage: float

    # Topic/keyword metrics
    top_keywords: List[Tuple[str, int]]  # (keyword, frequency)
    emerging_keywords: List[str]
    declining_keywords: List[str]

    # Temporal metrics
    first_article_date: str
    articles_last_month: int
    articles_last_3_months: int
    articles_first_3_months: int
    growth_rate_early_vs_late: float

    # Data quality
    articles_with_content: int
    articles_with_description: int
    coverage_percentage: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class NewsMetricsCalculator:
    """Calculate metrics from News data for Hype Cycle analysis"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, technology_id: int) -> NewsMetricsSnapshot:
        """
        Calculate all metrics for a technology's news articles

        Args:
            technology_id: ID of technology to analyze

        Returns:
            NewsMetricsSnapshot with all calculated metrics
        """
        logger.info(f"Starting News metrics calculation for technology {technology_id}")

        # Fetch all articles for this technology
        articles = self.db.query(NewsArticle)\
            .filter(NewsArticle.technology_id == technology_id)\
            .order_by(NewsArticle.published_at)\
            .all()

        if not articles:
            raise ValueError(f"No news articles found for technology {technology_id}")

        if len(articles) < 10:
            raise ValueError(f"Insufficient articles for analysis. Found {len(articles)}, need at least 10.")

        logger.info(f"Found {len(articles)} news articles to analyze")

        # Calculate each metric category
        volume_metrics = self._calculate_volume_metrics(articles)
        source_metrics = self._calculate_source_metrics(articles)
        author_metrics = self._calculate_author_metrics(articles)
        topic_metrics = self._calculate_topic_metrics(articles)
        temporal_metrics = self._calculate_temporal_metrics(articles)
        quality_metrics = self._calculate_quality_metrics(articles)

        # Combine into snapshot
        metrics = NewsMetricsSnapshot(
            **volume_metrics,
            **source_metrics,
            **author_metrics,
            **topic_metrics,
            **temporal_metrics,
            **quality_metrics
        )

        logger.info("News metrics calculation completed")
        return metrics

    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO 8601 date string to datetime"""
        if not date_str:
            return None
        try:
            # Handle various ISO 8601 formats
            if 'T' in date_str:
                # Remove 'Z' suffix if present
                date_str = date_str.replace('Z', '+00:00')
                # Handle timezone
                if '+' in date_str:
                    date_str = date_str.split('+')[0]
                return datetime.fromisoformat(date_str)
            else:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    def _calculate_volume_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Calculate article volume and velocity metrics"""
        logger.info("Calculating News volume metrics...")

        # Group by year-month
        month_counts = defaultdict(int)
        for article in articles:
            dt = self._parse_date(article.published_at)
            if dt:
                month_key = f"{dt.year}-{dt.month:02d}"
                month_counts[month_key] += 1

        # Sort months
        sorted_months = sorted(month_counts.keys())

        if not sorted_months:
            raise ValueError("No articles with date information")

        # Find peak
        peak_month = max(month_counts, key=month_counts.get)
        peak_count = month_counts[peak_month]

        # Calculate trend
        if len(sorted_months) >= 6:
            recent_3m = sum(month_counts[m] for m in sorted_months[-3:]) / 3
            earlier_3m = sum(month_counts[m] for m in sorted_months[:3]) / 3

            if recent_3m > earlier_3m * 1.2:
                trend = "increasing"
            elif recent_3m < earlier_3m * 0.8:
                trend = "decreasing"
            elif peak_month in sorted_months[-3:]:
                trend = "peak_reached"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Recent velocity (last 3 months)
        recent_velocity = sum(month_counts[m] for m in sorted_months[-3:]) / min(3, len(sorted_months))

        return {
            "total_articles": len(articles),
            "article_velocity": dict(month_counts),
            "velocity_trend": trend,
            "avg_articles_per_month": len(articles) / max(len(sorted_months), 1),
            "peak_month": peak_month,
            "peak_count": peak_count,
            "recent_velocity": recent_velocity
        }

    def _calculate_source_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Calculate source distribution metrics"""
        logger.info("Calculating News source metrics...")

        source_counts = Counter()
        for article in articles:
            source = article.source
            source_name = source.get("name", "unknown") if source else "unknown"
            source_counts[source_name] += 1

        unique_sources = len(source_counts)
        top_sources = source_counts.most_common(10)

        # Calculate HHI
        hhi = self._calculate_hhi(source_counts)

        return {
            "unique_sources": unique_sources,
            "top_sources": top_sources,
            "source_concentration_hhi": hhi
        }

    def _calculate_author_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Calculate author distribution metrics"""
        logger.info("Calculating News author metrics...")

        author_counts = Counter()
        without_author = 0

        for article in articles:
            author = article.author
            if author and author.strip():
                author_counts[author] += 1
            else:
                without_author += 1

        unique_authors = len(author_counts)
        top_authors = author_counts.most_common(10)
        without_author_pct = (without_author / len(articles)) * 100

        return {
            "unique_authors": unique_authors,
            "top_authors": top_authors,
            "articles_without_author_percentage": without_author_pct
        }

    def _calculate_hhi(self, counts: Dict[str, int]) -> float:
        """
        Calculate Herfindahl-Hirschman Index (HHI)

        HHI = sum of squared market shares
        Range: 0 (perfect competition) to 1 (monopoly)
        """
        total = sum(counts.values())
        if total == 0:
            return 0.0

        hhi = sum((count / total) ** 2 for count in counts.values())
        return hhi

    def _calculate_topic_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Extract and analyze keywords from titles/descriptions"""
        logger.info("Calculating News topic metrics...")

        all_text = []
        for article in articles:
            if article.title:
                all_text.append(article.title.lower())
            if article.description:
                all_text.append(article.description.lower())
            if article.content:
                all_text.append(article.content.lower())

        # Extract keywords
        words = Counter()
        for text in all_text:
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            words.update(tokens)

        # Filter stopwords
        stopwords = {
            "this", "that", "with", "from", "were", "have", "been", "their",
            "which", "these", "more", "other", "such", "into", "only", "also",
            "than", "some", "time", "very", "when", "them", "they", "there",
            "where", "what", "about", "after", "before", "would", "could",
            "should", "being", "between", "through", "during", "using",
            "said", "says", "will", "year", "years", "according", "news",
            "report", "reported", "reports", "article", "read", "more"
        }
        top_keywords = [(w, c) for w, c in words.most_common(50) if w not in stopwords]

        # Compare recent vs old articles for emerging/declining keywords
        midpoint = len(articles) // 2
        old_articles = articles[:midpoint]
        recent_articles = articles[midpoint:]

        old_words = Counter()
        recent_words = Counter()

        for article in old_articles:
            text = (article.title or "").lower() + " " + (article.description or "").lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            old_words.update(tokens)

        for article in recent_articles:
            text = (article.title or "").lower() + " " + (article.description or "").lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            recent_words.update(tokens)

        # Emerging keywords
        emerging_keywords = []
        for word, recent_count in recent_words.most_common(30):
            if word not in stopwords:
                old_count = old_words.get(word, 0)
                if recent_count > old_count * 2 and recent_count >= 5:
                    emerging_keywords.append(word)

        # Declining keywords
        declining_keywords = []
        for word, old_count in old_words.most_common(30):
            if word not in stopwords:
                recent_count = recent_words.get(word, 0)
                if old_count > recent_count * 2 and old_count >= 5:
                    declining_keywords.append(word)

        return {
            "top_keywords": top_keywords[:20],
            "emerging_keywords": emerging_keywords[:10],
            "declining_keywords": declining_keywords[:10]
        }

    def _calculate_temporal_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Calculate time-based comparison metrics"""
        logger.info("Calculating News temporal metrics...")

        # Get dates
        dates = []
        for article in articles:
            dt = self._parse_date(article.published_at)
            if dt:
                dates.append(dt)

        if not dates:
            return {
                "first_article_date": "unknown",
                "articles_last_month": 0,
                "articles_last_3_months": 0,
                "articles_first_3_months": 0,
                "growth_rate_early_vs_late": 0.0
            }

        first_date = min(dates)
        first_date_str = first_date.strftime("%Y-%m-%d")

        # Current time reference
        now = datetime.now()
        one_month_ago = now.timestamp() - (30 * 24 * 60 * 60)
        three_months_ago = now.timestamp() - (90 * 24 * 60 * 60)
        three_months_after_first = first_date.timestamp() + (90 * 24 * 60 * 60)

        articles_last_month = sum(1 for dt in dates if dt.timestamp() >= one_month_ago)
        articles_last_3_months = sum(1 for dt in dates if dt.timestamp() >= three_months_ago)
        articles_first_3_months = sum(1 for dt in dates if dt.timestamp() <= three_months_after_first)

        # Growth rate
        if articles_first_3_months > 0:
            growth_rate = ((articles_last_3_months - articles_first_3_months) / articles_first_3_months) * 100
        else:
            growth_rate = 0.0

        return {
            "first_article_date": first_date_str,
            "articles_last_month": articles_last_month,
            "articles_last_3_months": articles_last_3_months,
            "articles_first_3_months": articles_first_3_months,
            "growth_rate_early_vs_late": growth_rate
        }

    def _calculate_quality_metrics(self, articles: List[NewsArticle]) -> Dict:
        """Calculate data quality metrics"""
        logger.info("Calculating News data quality metrics...")

        total = len(articles)
        with_content = sum(1 for a in articles if a.content)
        with_description = sum(1 for a in articles if a.description)
        coverage = ((with_content + with_description) / (total * 2)) * 100

        return {
            "articles_with_content": with_content,
            "articles_with_description": with_description,
            "coverage_percentage": coverage
        }
