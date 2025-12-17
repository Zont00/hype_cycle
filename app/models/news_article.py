from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

from ..database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # NewsAPI fields - Basic
    article_id = Column(String(100), nullable=False, index=True)  # MD5 hash of URL
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)  # Full content (truncated to 200 chars on free tier)
    url = Column(String(1000), nullable=False)
    url_to_image = Column(String(1000), nullable=True)
    published_at = Column(String(30), nullable=True)  # ISO 8601 format
    author = Column(String(500), nullable=True)

    # Source metadata (stored as JSON)
    _source = Column("source", Text, nullable=True)  # {"id": "...", "name": "..."}

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="news_articles")

    # Composite unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_tech_article', 'technology_id', 'article_id', unique=True),
    )

    # Property methods for source (dict)
    @property
    def source(self):
        """Get source as Python dict"""
        if self._source:
            return json.loads(self._source)
        return {}

    @source.setter
    def source(self, value):
        """Set source from Python dict"""
        if value is None or value == {}:
            self._source = None
        else:
            self._source = json.dumps(value)

    def __repr__(self):
        return f"<NewsArticle(id={self.id}, article_id='{self.article_id}', title='{self.title[:50]}...')>"
