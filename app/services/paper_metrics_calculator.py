from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import defaultdict, Counter
import numpy as np
import re
import logging

from ..models import Paper

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Snapshot of all calculated metrics"""
    # Publication velocity metrics
    publication_velocity: Dict[int, int]  # year -> count
    velocity_trend: str  # "increasing", "decreasing", "stable", "peak_reached"
    avg_papers_per_year: float
    peak_year: int
    peak_count: int
    recent_velocity: float  # papers/year in last 2 years

    # Citation metrics
    total_citations: int
    avg_citations_per_paper: float
    median_citations: float
    citation_growth_rate: float  # % change year-over-year
    highly_cited_count: int  # papers with citations > threshold

    # Research type distribution
    basic_research_percentage: float
    applied_research_percentage: float
    mixed_research_percentage: float
    research_type_trend: str  # "toward_applied", "toward_basic", "stable"

    # Topic/keyword metrics
    top_keywords: List[Tuple[str, int]]  # (keyword, frequency)
    emerging_keywords: List[str]  # keywords appearing in recent papers
    declining_keywords: List[str]  # keywords disappearing

    # Venue distribution
    academic_venue_percentage: float
    industry_venue_percentage: float
    conference_percentage: float
    journal_percentage: float

    # Temporal metrics
    papers_last_year: int
    papers_last_2_years: int
    papers_first_2_years: int
    growth_rate_early_vs_late: float  # comparison

    # Data quality
    papers_with_abstracts: int
    papers_with_pdf: int
    coverage_percentage: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class PaperMetricsCalculator:
    """Calculate metrics from paper data for Hype Cycle analysis"""

    # Keyword lists for research type classification
    BASIC_SCIENCE_KEYWORDS = [
        "mechanism", "pathway", "fundamental", "theoretical", "discovery",
        "novel", "characterization", "identification", "isolation", "purification",
        "analysis of", "role of", "function of", "expression of", "regulation of",
        "molecular", "cellular", "biochemical", "genetics", "genomics",
        "proteomics", "metabolomics", "in vitro", "model system", "structure",
        "evolution", "phylogeny", "diversity", "morphology", "physiology"
    ]

    APPLIED_RESEARCH_KEYWORDS = [
        "application", "production", "optimization", "yield", "efficiency",
        "commercial", "industrial", "scalable", "scale-up", "process", "manufacturing",
        "product", "development", "implementation", "protocol", "method",
        "therapeutic", "treatment", "drug", "bioactive", "functional food",
        "bioreactor", "cultivation", "cost-effective", "sustainable production",
        "market", "industry", "economic", "practical", "clinical", "pilot scale"
    ]

    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, technology_id: int) -> MetricsSnapshot:
        """
        Calculate all metrics for a technology

        Args:
            technology_id: ID of technology to analyze

        Returns:
            MetricsSnapshot with all calculated metrics
        """
        logger.info(f"Starting metrics calculation for technology {technology_id}")

        # Fetch all papers for this technology
        papers = self.db.query(Paper)\
            .filter(Paper.technology_id == technology_id)\
            .order_by(Paper.year)\
            .all()

        if not papers:
            raise ValueError(f"No papers found for technology {technology_id}")

        logger.info(f"Found {len(papers)} papers to analyze")

        # Calculate each metric category
        velocity_metrics = self._calculate_velocity_metrics(papers)
        citation_metrics = self._calculate_citation_metrics(papers)
        research_type_metrics = self._calculate_research_type_distribution(papers)
        topic_metrics = self._calculate_topic_metrics(papers)
        venue_metrics = self._calculate_venue_distribution(papers)
        temporal_metrics = self._calculate_temporal_metrics(papers)
        quality_metrics = self._calculate_quality_metrics(papers)

        # Combine into snapshot
        metrics = MetricsSnapshot(
            **velocity_metrics,
            **citation_metrics,
            **research_type_metrics,
            **topic_metrics,
            **venue_metrics,
            **temporal_metrics,
            **quality_metrics
        )

        logger.info("Metrics calculation completed")
        return metrics

    def _calculate_velocity_metrics(self, papers: List[Paper]) -> Dict:
        """Calculate publication velocity and trends"""
        logger.info("Calculating velocity metrics...")

        # Group by year
        year_counts = defaultdict(int)
        for paper in papers:
            if paper.year:
                year_counts[paper.year] += 1

        # Sort years
        sorted_years = sorted(year_counts.keys())

        if not sorted_years:
            raise ValueError("No papers with year information")

        # Find peak
        peak_year = max(year_counts, key=year_counts.get)
        peak_count = year_counts[peak_year]

        # Calculate trend
        if len(sorted_years) >= 3:
            recent_3yr = sum(year_counts[y] for y in sorted_years[-3:]) / 3
            earlier_3yr = sum(year_counts[y] for y in sorted_years[:3]) / 3

            if recent_3yr > earlier_3yr * 1.2:
                trend = "increasing"
            elif recent_3yr < earlier_3yr * 0.8:
                trend = "decreasing"
            elif peak_year in sorted_years[-3:]:
                trend = "peak_reached"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Recent velocity (last 2 years)
        current_year = datetime.now().year
        recent_years = [y for y in sorted_years if y >= current_year - 2]
        recent_velocity = sum(year_counts[y] for y in recent_years) / max(len(recent_years), 1)

        return {
            "publication_velocity": dict(year_counts),
            "velocity_trend": trend,
            "avg_papers_per_year": len(papers) / max(len(sorted_years), 1),
            "peak_year": peak_year,
            "peak_count": peak_count,
            "recent_velocity": recent_velocity
        }

    def _calculate_citation_metrics(self, papers: List[Paper]) -> Dict:
        """Calculate citation-based metrics"""
        logger.info("Calculating citation metrics...")

        citations = [p.citation_count for p in papers if p.citation_count is not None]

        if not citations:
            return {
                "total_citations": 0,
                "avg_citations_per_paper": 0.0,
                "median_citations": 0.0,
                "citation_growth_rate": 0.0,
                "highly_cited_count": 0
            }

        # Basic stats
        total = sum(citations)
        avg = total / len(citations)
        median = float(np.median(citations))

        # Highly cited threshold (top 10% or 100+ citations)
        threshold = max(100, np.percentile(citations, 90))
        highly_cited = sum(1 for c in citations if c >= threshold)

        # Citation growth rate (year-over-year)
        year_avg_citations = {}
        for paper in papers:
            if paper.year and paper.citation_count is not None:
                if paper.year not in year_avg_citations:
                    year_avg_citations[paper.year] = []
                year_avg_citations[paper.year].append(paper.citation_count)

        # Calculate growth rate
        if len(year_avg_citations) >= 2:
            years = sorted(year_avg_citations.keys())
            recent_avg = np.mean(year_avg_citations[years[-1]])
            earlier_avg = np.mean(year_avg_citations[years[-2]])
            growth_rate = ((recent_avg - earlier_avg) / max(earlier_avg, 1)) * 100
        else:
            growth_rate = 0.0

        return {
            "total_citations": total,
            "avg_citations_per_paper": avg,
            "median_citations": median,
            "citation_growth_rate": growth_rate,
            "highly_cited_count": highly_cited
        }

    def _calculate_research_type_distribution(self, papers: List[Paper]) -> Dict:
        """
        Classify papers as basic science vs applied research

        Strategy:
        - Extract keywords from titles and abstracts
        - Match against basic science and applied research keyword lists
        - Calculate percentage distribution
        """
        logger.info("Calculating research type distribution...")

        basic_count = 0
        applied_count = 0
        mixed_count = 0

        for paper in papers:
            classification = self._classify_research_type(paper)
            if classification == "basic":
                basic_count += 1
            elif classification == "applied":
                applied_count += 1
            else:
                mixed_count += 1

        total = len(papers)
        basic_pct = (basic_count / total) * 100
        applied_pct = (applied_count / total) * 100
        mixed_pct = (mixed_count / total) * 100

        # Determine trend: compare first half vs second half
        midpoint = total // 2
        first_half = papers[:midpoint]
        second_half = papers[midpoint:]

        first_applied = sum(1 for p in first_half if self._classify_research_type(p) == "applied")
        second_applied = sum(1 for p in second_half if self._classify_research_type(p) == "applied")

        first_applied_pct = (first_applied / len(first_half)) * 100 if first_half else 0
        second_applied_pct = (second_applied / len(second_half)) * 100 if second_half else 0

        if second_applied_pct > first_applied_pct + 10:
            trend = "toward_applied"
        elif second_applied_pct < first_applied_pct - 10:
            trend = "toward_basic"
        else:
            trend = "stable"

        logger.info(f"Research type: Basic={basic_pct:.1f}%, Applied={applied_pct:.1f}%, Mixed={mixed_pct:.1f}%")

        return {
            "basic_research_percentage": basic_pct,
            "applied_research_percentage": applied_pct,
            "mixed_research_percentage": mixed_pct,
            "research_type_trend": trend
        }

    def _classify_research_type(self, paper: Paper) -> str:
        """
        Classify a single paper as basic, applied, or mixed

        Returns: "basic", "applied", or "mixed"
        """
        text = (paper.title or "").lower() + " " + (paper.abstract or "").lower()

        basic_score = sum(1 for kw in self.BASIC_SCIENCE_KEYWORDS if kw in text)
        applied_score = sum(1 for kw in self.APPLIED_RESEARCH_KEYWORDS if kw in text)

        # Classification logic
        if basic_score > applied_score * 2:
            return "basic"
        elif applied_score > basic_score * 2:
            return "applied"
        else:
            return "mixed"

    def _calculate_topic_metrics(self, papers: List[Paper]) -> Dict:
        """Extract and analyze keywords from titles/abstracts"""
        logger.info("Calculating topic metrics...")

        all_text = []
        for paper in papers:
            if paper.abstract:
                all_text.append(paper.abstract.lower())
            if paper.title:
                all_text.append(paper.title.lower())

        # Extract keywords (simple approach: frequent meaningful words)
        words = Counter()
        for text in all_text:
            # Remove common words, extract meaningful terms (4+ letters)
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            words.update(tokens)

        # Filter out common stopwords
        stopwords = {
            "this", "that", "with", "from", "were", "have", "been", "their",
            "which", "these", "more", "other", "such", "into", "only", "also",
            "than", "some", "time", "very", "when", "them", "they", "there",
            "where", "what", "about", "after", "before", "would", "could",
            "should", "being", "between", "through", "during", "using"
        }
        top_keywords = [(w, c) for w, c in words.most_common(50) if w not in stopwords]

        # For emerging/declining keywords, compare recent vs old papers
        # Split papers into two periods
        midpoint = len(papers) // 2
        old_papers = papers[:midpoint]
        recent_papers = papers[midpoint:]

        old_words = Counter()
        recent_words = Counter()

        for paper in old_papers:
            text = (paper.title or "").lower() + " " + (paper.abstract or "").lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            old_words.update(tokens)

        for paper in recent_papers:
            text = (paper.title or "").lower() + " " + (paper.abstract or "").lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            recent_words.update(tokens)

        # Emerging: words that appear much more frequently in recent papers
        emerging_keywords = []
        for word, recent_count in recent_words.most_common(30):
            if word not in stopwords:
                old_count = old_words.get(word, 0)
                if recent_count > old_count * 2 and recent_count >= 10:
                    emerging_keywords.append(word)

        # Declining: words that appeared frequently in old but not in recent
        declining_keywords = []
        for word, old_count in old_words.most_common(30):
            if word not in stopwords:
                recent_count = recent_words.get(word, 0)
                if old_count > recent_count * 2 and old_count >= 10:
                    declining_keywords.append(word)

        return {
            "top_keywords": top_keywords[:20],
            "emerging_keywords": emerging_keywords[:10],
            "declining_keywords": declining_keywords[:10]
        }

    def _calculate_venue_distribution(self, papers: List[Paper]) -> Dict:
        """Analyze publication venues"""
        logger.info("Calculating venue distribution...")

        # Keywords to identify venue types
        academic_keywords = ["journal", "proceedings", "transactions", "letters", "review"]
        industry_keywords = ["industrial", "applied", "engineering", "technology", "biotechnology"]
        conference_keywords = ["conference", "symposium", "workshop", "proceedings", "meeting"]

        academic_count = 0
        industry_count = 0
        conference_count = 0
        journal_count = 0

        for paper in papers:
            venue = (paper.venue or "").lower()

            if any(kw in venue for kw in conference_keywords):
                conference_count += 1
            else:
                journal_count += 1

            if any(kw in venue for kw in industry_keywords):
                industry_count += 1
            else:
                academic_count += 1

        total = len(papers)

        return {
            "academic_venue_percentage": (academic_count / total) * 100,
            "industry_venue_percentage": (industry_count / total) * 100,
            "conference_percentage": (conference_count / total) * 100,
            "journal_percentage": (journal_count / total) * 100
        }

    def _calculate_temporal_metrics(self, papers: List[Paper]) -> Dict:
        """Calculate time-based comparison metrics"""
        logger.info("Calculating temporal metrics...")

        current_year = datetime.now().year

        papers_last_year = sum(1 for p in papers if p.year == current_year - 1)
        papers_last_2_years = sum(1 for p in papers if p.year and p.year >= current_year - 2)

        # Get earliest years
        years = sorted([p.year for p in papers if p.year])
        if years:
            earliest_year = years[0]
            papers_first_2_years = sum(1 for p in papers if p.year and p.year <= earliest_year + 2)

            # Growth rate comparison
            if papers_first_2_years > 0:
                growth_rate = ((papers_last_2_years - papers_first_2_years) / papers_first_2_years) * 100
            else:
                growth_rate = 0.0
        else:
            papers_first_2_years = 0
            growth_rate = 0.0

        return {
            "papers_last_year": papers_last_year,
            "papers_last_2_years": papers_last_2_years,
            "papers_first_2_years": papers_first_2_years,
            "growth_rate_early_vs_late": growth_rate
        }

    def _calculate_quality_metrics(self, papers: List[Paper]) -> Dict:
        """Calculate data quality and coverage metrics"""
        logger.info("Calculating quality metrics...")

        total = len(papers)
        with_abstracts = sum(1 for p in papers if p.abstract)
        with_pdf = sum(1 for p in papers if p.open_access_pdf)

        coverage = ((with_abstracts + with_pdf) / (total * 2)) * 100

        return {
            "papers_with_abstracts": with_abstracts,
            "papers_with_pdf": with_pdf,
            "coverage_percentage": coverage
        }
