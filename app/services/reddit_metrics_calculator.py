from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from collections import defaultdict, Counter
import numpy as np
import re
import logging

from ..models import RedditPost

logger = logging.getLogger(__name__)


@dataclass
class RedditMetricsSnapshot:
    """Snapshot of all calculated Reddit metrics"""
    # Volume metrics
    total_posts: int
    post_velocity: Dict[str, int]  # year-month -> count
    velocity_trend: str  # "increasing", "decreasing", "stable", "peak_reached"
    avg_posts_per_month: float
    peak_month: str
    peak_count: int
    recent_velocity: float  # posts/month in last 3 months

    # Engagement metrics
    total_score: int
    avg_score_per_post: float
    median_score: float
    total_comments: int
    avg_comments_per_post: float
    median_comments: float
    engagement_trend: str  # "increasing", "decreasing", "stable"
    highly_engaged_count: int  # posts with score > threshold

    # Subreddit distribution
    unique_subreddits: int
    top_subreddits: List[Tuple[str, int]]  # (subreddit, count)
    subreddit_concentration_hhi: float  # 0-1, Herfindahl-Hirschman Index

    # Author metrics
    unique_authors: int
    top_authors: List[Tuple[str, int]]  # (author, count)
    author_concentration_hhi: float

    # Post type distribution
    self_post_percentage: float
    link_post_percentage: float

    # Topic/keyword metrics
    top_keywords: List[Tuple[str, int]]  # (keyword, frequency)
    emerging_keywords: List[str]
    declining_keywords: List[str]

    # Temporal metrics
    first_post_date: str
    posts_last_month: int
    posts_last_3_months: int
    posts_first_3_months: int
    growth_rate_early_vs_late: float

    # Data quality
    posts_with_body: int
    coverage_percentage: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class RedditMetricsCalculator:
    """Calculate metrics from Reddit data for Hype Cycle analysis"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, technology_id: int) -> RedditMetricsSnapshot:
        """
        Calculate all metrics for a technology's Reddit posts

        Args:
            technology_id: ID of technology to analyze

        Returns:
            RedditMetricsSnapshot with all calculated metrics
        """
        logger.info(f"Starting Reddit metrics calculation for technology {technology_id}")

        # Fetch all posts for this technology
        posts = self.db.query(RedditPost)\
            .filter(RedditPost.technology_id == technology_id)\
            .order_by(RedditPost.created_utc)\
            .all()

        if not posts:
            raise ValueError(f"No Reddit posts found for technology {technology_id}")

        if len(posts) < 10:
            raise ValueError(f"Insufficient posts for analysis. Found {len(posts)}, need at least 10.")

        logger.info(f"Found {len(posts)} Reddit posts to analyze")

        # Calculate each metric category
        volume_metrics = self._calculate_volume_metrics(posts)
        engagement_metrics = self._calculate_engagement_metrics(posts)
        subreddit_metrics = self._calculate_subreddit_metrics(posts)
        author_metrics = self._calculate_author_metrics(posts)
        type_metrics = self._calculate_type_metrics(posts)
        topic_metrics = self._calculate_topic_metrics(posts)
        temporal_metrics = self._calculate_temporal_metrics(posts)
        quality_metrics = self._calculate_quality_metrics(posts)

        # Combine into snapshot
        metrics = RedditMetricsSnapshot(
            **volume_metrics,
            **engagement_metrics,
            **subreddit_metrics,
            **author_metrics,
            **type_metrics,
            **topic_metrics,
            **temporal_metrics,
            **quality_metrics
        )

        logger.info("Reddit metrics calculation completed")
        return metrics

    def _calculate_volume_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate post volume and velocity metrics"""
        logger.info("Calculating Reddit volume metrics...")

        # Group by year-month
        month_counts = defaultdict(int)
        for post in posts:
            if post.created_utc:
                dt = datetime.fromtimestamp(post.created_utc)
                month_key = f"{dt.year}-{dt.month:02d}"
                month_counts[month_key] += 1

        # Sort months
        sorted_months = sorted(month_counts.keys())

        if not sorted_months:
            raise ValueError("No posts with timestamp information")

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
            "total_posts": len(posts),
            "post_velocity": dict(month_counts),
            "velocity_trend": trend,
            "avg_posts_per_month": len(posts) / max(len(sorted_months), 1),
            "peak_month": peak_month,
            "peak_count": peak_count,
            "recent_velocity": recent_velocity
        }

    def _calculate_engagement_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate engagement-based metrics (score, comments)"""
        logger.info("Calculating Reddit engagement metrics...")

        scores = [p.score for p in posts if p.score is not None]
        comments = [p.num_comments for p in posts if p.num_comments is not None]

        if not scores:
            scores = [0]
        if not comments:
            comments = [0]

        # Score stats
        total_score = sum(scores)
        avg_score = total_score / len(scores)
        median_score = float(np.median(scores))

        # Comment stats
        total_comments = sum(comments)
        avg_comments = total_comments / len(comments)
        median_comments = float(np.median(comments))

        # Highly engaged threshold (top 10% or 100+ score)
        threshold = max(100, np.percentile(scores, 90)) if len(scores) > 1 else 100
        highly_engaged = sum(1 for s in scores if s >= threshold)

        # Engagement trend: compare first half vs second half
        midpoint = len(posts) // 2
        first_half_scores = [p.score or 0 for p in posts[:midpoint]]
        second_half_scores = [p.score or 0 for p in posts[midpoint:]]

        if first_half_scores and second_half_scores:
            first_avg = np.mean(first_half_scores)
            second_avg = np.mean(second_half_scores)

            if second_avg > first_avg * 1.2:
                engagement_trend = "increasing"
            elif second_avg < first_avg * 0.8:
                engagement_trend = "decreasing"
            else:
                engagement_trend = "stable"
        else:
            engagement_trend = "insufficient_data"

        return {
            "total_score": total_score,
            "avg_score_per_post": avg_score,
            "median_score": median_score,
            "total_comments": total_comments,
            "avg_comments_per_post": avg_comments,
            "median_comments": median_comments,
            "engagement_trend": engagement_trend,
            "highly_engaged_count": highly_engaged
        }

    def _calculate_subreddit_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate subreddit distribution metrics"""
        logger.info("Calculating Reddit subreddit metrics...")

        subreddit_counts = Counter()
        for post in posts:
            subreddit = post.subreddit or "unknown"
            subreddit_counts[subreddit] += 1

        unique_subreddits = len(subreddit_counts)
        top_subreddits = subreddit_counts.most_common(10)

        # Calculate HHI
        hhi = self._calculate_hhi(subreddit_counts)

        return {
            "unique_subreddits": unique_subreddits,
            "top_subreddits": top_subreddits,
            "subreddit_concentration_hhi": hhi
        }

    def _calculate_author_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate author distribution metrics"""
        logger.info("Calculating Reddit author metrics...")

        author_counts = Counter()
        for post in posts:
            author = post.author or "[deleted]"
            author_counts[author] += 1

        unique_authors = len(author_counts)
        top_authors = author_counts.most_common(10)

        # Calculate HHI
        hhi = self._calculate_hhi(author_counts)

        return {
            "unique_authors": unique_authors,
            "top_authors": top_authors,
            "author_concentration_hhi": hhi
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

    def _calculate_type_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate post type distribution metrics"""
        logger.info("Calculating Reddit post type metrics...")

        self_count = sum(1 for p in posts if p.post_type == "self")
        link_count = sum(1 for p in posts if p.post_type == "link")
        total = len(posts)

        return {
            "self_post_percentage": (self_count / total) * 100,
            "link_post_percentage": (link_count / total) * 100
        }

    def _calculate_topic_metrics(self, posts: List[RedditPost]) -> Dict:
        """Extract and analyze keywords from titles/body"""
        logger.info("Calculating Reddit topic metrics...")

        all_text = []
        for post in posts:
            if post.title:
                all_text.append(post.title.lower())
            if post.selftext:
                all_text.append(post.selftext.lower())

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
            "just", "like", "know", "think", "want", "really", "anyone",
            "something", "getting", "going", "looking", "reddit", "post"
        }
        top_keywords = [(w, c) for w, c in words.most_common(50) if w not in stopwords]

        # Compare recent vs old posts for emerging/declining keywords
        midpoint = len(posts) // 2
        old_posts = posts[:midpoint]
        recent_posts = posts[midpoint:]

        old_words = Counter()
        recent_words = Counter()

        for post in old_posts:
            text = (post.title or "").lower() + " " + (post.selftext or "").lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            old_words.update(tokens)

        for post in recent_posts:
            text = (post.title or "").lower() + " " + (post.selftext or "").lower()
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

    def _calculate_temporal_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate time-based comparison metrics"""
        logger.info("Calculating Reddit temporal metrics...")

        # Get timestamps
        timestamps = [p.created_utc for p in posts if p.created_utc]

        if not timestamps:
            return {
                "first_post_date": "unknown",
                "posts_last_month": 0,
                "posts_last_3_months": 0,
                "posts_first_3_months": 0,
                "growth_rate_early_vs_late": 0.0
            }

        first_ts = min(timestamps)
        first_date = datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d")

        # Current time reference
        now = datetime.now().timestamp()
        one_month_ago = now - (30 * 24 * 60 * 60)
        three_months_ago = now - (90 * 24 * 60 * 60)
        three_months_after_first = first_ts + (90 * 24 * 60 * 60)

        posts_last_month = sum(1 for ts in timestamps if ts >= one_month_ago)
        posts_last_3_months = sum(1 for ts in timestamps if ts >= three_months_ago)
        posts_first_3_months = sum(1 for ts in timestamps if ts <= three_months_after_first)

        # Growth rate
        if posts_first_3_months > 0:
            growth_rate = ((posts_last_3_months - posts_first_3_months) / posts_first_3_months) * 100
        else:
            growth_rate = 0.0

        return {
            "first_post_date": first_date,
            "posts_last_month": posts_last_month,
            "posts_last_3_months": posts_last_3_months,
            "posts_first_3_months": posts_first_3_months,
            "growth_rate_early_vs_late": growth_rate
        }

    def _calculate_quality_metrics(self, posts: List[RedditPost]) -> Dict:
        """Calculate data quality metrics"""
        logger.info("Calculating Reddit data quality metrics...")

        total = len(posts)
        with_body = sum(1 for p in posts if p.selftext)
        coverage = (with_body / total) * 100

        return {
            "posts_with_body": with_body,
            "coverage_percentage": coverage
        }
