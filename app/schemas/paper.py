from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class PaperBase(BaseModel):
    """Base schema with common paper fields"""
    paper_id: str = Field(..., max_length=40, description="Semantic Scholar paper ID")
    title: str = Field(..., description="Paper title")
    year: Optional[int] = Field(None, ge=1900, le=2100, description="Publication year")
    citation_count: Optional[int] = Field(None, ge=0, description="Number of citations")
    publication_date: Optional[str] = Field(None, max_length=10, description="Publication date (YYYY-MM-DD)")

    # Extended fields
    abstract: Optional[str] = Field(None, description="Paper abstract")
    authors: Optional[List[Any]] = Field(None, description="List of authors")
    venue: Optional[str] = Field(None, description="Publication venue")
    s2_fields_of_study: Optional[List[Any]] = Field(None, description="Semantic Scholar fields of study")
    open_access_pdf: Optional[str] = Field(None, description="URL to open access PDF")


class PaperCreate(PaperBase):
    """Schema for creating a new paper"""
    technology_id: int = Field(..., gt=0, description="Technology ID")


class PaperResponse(PaperBase):
    """Schema for paper response"""
    id: int
    technology_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CollectionStats(BaseModel):
    """Response schema for collection operation"""
    technology_id: int
    technology_name: str
    papers_collected: int
    total_papers_found: int
    batches_processed: int
    new_papers: int
    duplicate_papers: int
    errors: Optional[List[str]] = None
