from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class AnalysisResponse(BaseModel):
    """Response schema for Hype Cycle analysis"""
    id: int
    technology_id: int
    current_phase: str
    phase_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    analysis_date: datetime
    total_papers_analyzed: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    metrics: Dict[str, Any]
    rule_scores: Optional[Dict[str, float]] = None
    rationale: Optional[str] = None

    class Config:
        from_attributes = True


class AnalysisStats(BaseModel):
    """Statistics from analysis process"""
    technology_id: int
    technology_name: str
    phase_determined: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    papers_analyzed: int
    analysis_timestamp: datetime
