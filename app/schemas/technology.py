from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TechnologyBase(BaseModel):
    """Base schema with common fields"""
    name: str = Field(..., min_length=1, max_length=200, description="Technology name")
    description: Optional[str] = Field(None, description="Optional technology description")
    keywords: List[str] = Field(..., min_items=1, description="List of keywords for data collection")
    excluded_terms: Optional[List[str]] = Field(default=None, description="List of terms to exclude from search")
    tickers: Optional[List[str]] = Field(default=None, description="List of stock ticker symbols")


class TechnologyCreate(TechnologyBase):
    """Schema for creating a new technology"""
    pass


class TechnologyUpdate(BaseModel):
    """Schema for updating a technology (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    keywords: Optional[List[str]] = Field(None, min_items=1)
    excluded_terms: Optional[List[str]] = None
    tickers: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TechnologyResponse(TechnologyBase):
    """Schema for technology response (includes database fields)"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models
