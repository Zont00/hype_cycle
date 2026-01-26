from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class RedditAnalysisResponse(BaseModel):
    """Response schema for Reddit analysis"""
    technology_id: int
    analysis_date: datetime
    total_posts_analyzed: int

    # Phase determination
    current_phase: str
    phase_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    phase_scores: Optional[Dict[str, float]] = None
    rationale: Optional[str] = None

    # Volume metrics
    post_velocity: Dict[str, int]  # year-month -> count
    velocity_trend: str
    avg_posts_per_month: float
    peak_month: str
    peak_count: int
    recent_velocity: float

    # Engagement metrics
    total_score: int
    avg_score_per_post: float
    median_score: float
    total_comments: int
    avg_comments_per_post: float
    median_comments: float
    engagement_trend: str
    highly_engaged_count: int

    # Subreddit distribution
    unique_subreddits: int
    top_subreddits: List[List[Any]]  # List of [subreddit, count] pairs
    subreddit_concentration_hhi: float

    # Author metrics
    unique_authors: int
    top_authors: List[List[Any]]  # List of [author, count] pairs
    author_concentration_hhi: float

    # Post type distribution
    self_post_percentage: float
    link_post_percentage: float

    # Topic metrics
    top_keywords: List[List[Any]]  # List of [keyword, count] pairs
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

    class Config:
        from_attributes = True
