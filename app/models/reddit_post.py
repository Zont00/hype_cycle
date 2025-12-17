from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Reddit post fields - Basic
    post_id = Column(String(20), nullable=False, index=True)  # Reddit post ID (e.g., "abc123")
    title = Column(Text, nullable=False)
    selftext = Column(Text, nullable=True)  # Post body text (empty for link posts)
    score = Column(Integer, nullable=True, default=0)  # Upvotes - downvotes
    num_comments = Column(Integer, nullable=True, default=0)

    # Reddit post fields - Metadata
    author = Column(String(100), nullable=True)  # Username (can be [deleted])
    subreddit = Column(String(100), nullable=True)  # Subreddit name
    created_utc = Column(Integer, nullable=True)  # Unix timestamp
    permalink = Column(String(500), nullable=True)  # Reddit URL path
    url = Column(String(1000), nullable=True)  # Link URL (for link posts)
    post_type = Column(String(20), nullable=True)  # "self" or "link"

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="reddit_posts")

    # Composite unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_tech_reddit_post', 'technology_id', 'post_id', unique=True),
    )

    def __repr__(self):
        return f"<RedditPost(id={self.id}, post_id='{self.post_id}', title='{self.title[:50]}...')>"
