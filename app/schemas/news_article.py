from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class NewsArticleBase(BaseModel):
    """Base schema with common news article fields"""
    article_id: str = Field(..., max_length=100, description="Generated article ID (URL hash)")
    title: str = Field(..., description="Article title")
    description: Optional[str] = Field(None, description="Article description/summary")
    content: Optional[str] = Field(None, description="Article content (may be truncated to 200 chars)")
    url: str = Field(..., max_length=1000, description="Article URL")
    url_to_image: Optional[str] = Field(None, max_length=1000, description="Image URL")
    published_at: Optional[str] = Field(None, max_length=30, description="Publication timestamp (ISO 8601)")
    author: Optional[str] = Field(None, max_length=500, description="Article author(s)")
    source: Optional[Dict[str, Any]] = Field(None, description="Source metadata")


class NewsArticleCreate(NewsArticleBase):
    """Schema for creating a new news article"""
    technology_id: int = Field(..., gt=0, description="Technology ID")


class NewsArticleResponse(NewsArticleBase):
    """Schema for news article response"""
    id: int
    technology_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class NewsCollectionStats(BaseModel):
    """Response schema for news collection operation"""
    technology_id: int
    technology_name: str
    articles_collected: int
    total_articles_found: int
    batches_processed: int
    new_articles: int
    duplicate_articles: int
    errors: Optional[List[str]] = None
