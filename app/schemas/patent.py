from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class PatentBase(BaseModel):
    """Base schema with common patent fields"""
    patent_id: str = Field(..., max_length=20, description="US patent number")
    patent_title: str = Field(..., description="Patent title")
    patent_year: Optional[int] = Field(None, ge=1790, le=2100, description="Patent grant year")
    patent_date: Optional[str] = Field(None, max_length=10, description="Patent grant date (YYYY-MM-DD)")
    patent_abstract: Optional[str] = Field(None, description="Patent abstract")
    patent_type: Optional[str] = Field(None, max_length=50, description="Patent type (e.g., utility, design)")

    # Citation metrics
    patent_num_us_patents_cited: Optional[int] = Field(None, ge=0, description="Number of US patents cited by this patent")
    patent_num_times_cited_by_us_patents: Optional[int] = Field(None, ge=0, description="Number of times cited by other US patents")

    # Complex fields
    assignees: Optional[List[Any]] = Field(None, description="List of assignees")


class PatentCreate(PatentBase):
    """Schema for creating a new patent"""
    technology_id: int = Field(..., gt=0, description="Technology ID")


class PatentResponse(PatentBase):
    """Schema for patent response"""
    id: int
    technology_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PatentCollectionStats(BaseModel):
    """Response schema for patent collection operation"""
    technology_id: int
    technology_name: str
    patents_collected: int
    total_patents_found: int
    batches_processed: int
    new_patents: int
    duplicate_patents: int
    errors: Optional[List[str]] = None
