from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RedditPostBase(BaseModel):
    """Base schema with common Reddit post fields"""
    post_id: str = Field(..., max_length=20, description="Reddit post ID")
    title: str = Field(..., description="Post title")
    selftext: Optional[str] = Field(None, description="Post body text (self posts)")
    score: Optional[int] = Field(None, description="Post score (upvotes - downvotes)")
    num_comments: Optional[int] = Field(None, ge=0, description="Number of comments")

    # Metadata
    author: Optional[str] = Field(None, max_length=100, description="Author username")
    subreddit: Optional[str] = Field(None, max_length=100, description="Subreddit name")
    created_utc: Optional[int] = Field(None, ge=0, description="Creation timestamp (Unix UTC)")
    permalink: Optional[str] = Field(None, max_length=500, description="Reddit permalink")
    url: Optional[str] = Field(None, max_length=1000, description="Post URL (for link posts)")
    post_type: Optional[str] = Field(None, max_length=20, description="Post type (self or link)")


class RedditPostCreate(RedditPostBase):
    """Schema for creating a new Reddit post"""
    technology_id: int = Field(..., gt=0, description="Technology ID")


class RedditPostResponse(RedditPostBase):
    """Schema for Reddit post response"""
    id: int
    technology_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RedditCollectionStats(BaseModel):
    """Response schema for Reddit post collection operation"""
    technology_id: int
    technology_name: str
    posts_collected: int
    total_posts_found: int
    batches_processed: int
    new_posts: int
    duplicate_posts: int
    errors: Optional[List[str]] = None
