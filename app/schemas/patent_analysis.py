from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class PatentAnalysisResponse(BaseModel):
    """Response schema for patent analysis"""
    technology_id: int
    analysis_date: datetime
    total_patents_analyzed: int

    # Phase determination
    current_phase: str
    phase_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    phase_scores: Optional[Dict[str, float]] = None
    rationale: Optional[str] = None

    # Volume metrics
    patent_velocity: Dict[int, int]
    velocity_trend: str
    avg_patents_per_year: float
    peak_year: int
    peak_count: int
    recent_velocity: float

    # Citation metrics
    total_forward_citations: int
    total_backward_citations: int
    avg_forward_citations: float
    avg_backward_citations: float
    citation_ratio: float
    median_forward_citations: float
    highly_cited_count: int

    # Assignee metrics
    unique_assignees_count: int
    top_assignees: List[List[Any]]  # List of [name, count] pairs
    assignee_concentration_hhi: float
    corporate_percentage: float
    academic_percentage: float
    individual_percentage: float
    new_entrants_by_year: Dict[int, int]

    # Geographic metrics
    country_distribution: Dict[str, int]
    unique_countries: int
    top_countries: List[List[Any]]  # List of [country, count] pairs

    # Patent type metrics
    utility_percentage: float
    design_percentage: float
    other_type_percentage: float

    # Temporal metrics
    first_patent_year: int
    technology_age_years: int
    patents_last_year: int
    patents_last_2_years: int

    # Data quality
    patents_with_abstract: int
    coverage_percentage: float

    class Config:
        from_attributes = True
