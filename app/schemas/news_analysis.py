from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class NewsAnalysisResponse(BaseModel):
    """Response schema for News analysis"""
    technology_id: int
    analysis_date: datetime
    total_articles_analyzed: int

    # Phase determination
    current_phase: str
    phase_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    phase_scores: Optional[Dict[str, float]] = None
    rationale: Optional[str] = None

    # Volume metrics
    article_velocity: Dict[str, int]  # year-month -> count
    velocity_trend: str
    avg_articles_per_month: float
    peak_month: str
    peak_count: int
    recent_velocity: float

    # Source distribution
    unique_sources: int
    top_sources: List[List[Any]]  # List of [source, count] pairs
    source_concentration_hhi: float

    # Author metrics
    unique_authors: int
    top_authors: List[List[Any]]  # List of [author, count] pairs
    articles_without_author_percentage: float

    # Topic metrics
    top_keywords: List[List[Any]]  # List of [keyword, count] pairs
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

    class Config:
        from_attributes = True
