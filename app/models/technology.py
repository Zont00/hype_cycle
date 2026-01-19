from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

from ..database import Base


class Technology(Base):
    __tablename__ = "technologies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # JSON fields stored as TEXT
    _keywords = Column("keywords", Text, nullable=False)
    _excluded_terms = Column("excluded_terms", Text, nullable=True)
    _tickers = Column("tickers", Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to papers
    papers = relationship("Paper", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to patents
    patents = relationship("Patent", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to Reddit posts
    reddit_posts = relationship("RedditPost", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to news articles
    news_articles = relationship("NewsArticle", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to stock prices
    stock_prices = relationship("StockPrice", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to stock info
    stock_info = relationship("StockInfo", back_populates="technology", cascade="all, delete-orphan")

    # Relationship to analysis
    analysis = relationship("TechnologyAnalysis", back_populates="technology", uselist=False, cascade="all, delete-orphan")

    # Property methods for keywords (list of strings)
    @property
    def keywords(self):
        """Get keywords as Python list"""
        if self._keywords:
            return json.loads(self._keywords)
        return []

    @keywords.setter
    def keywords(self, value):
        """Set keywords from Python list"""
        if value is None:
            self._keywords = "[]"
        else:
            self._keywords = json.dumps(value)

    # Property methods for excluded_terms (list of strings)
    @property
    def excluded_terms(self):
        """Get excluded_terms as Python list"""
        if self._excluded_terms:
            return json.loads(self._excluded_terms)
        return []

    @excluded_terms.setter
    def excluded_terms(self, value):
        """Set excluded_terms from Python list"""
        if value is None or value == []:
            self._excluded_terms = None
        else:
            self._excluded_terms = json.dumps(value)

    # Property methods for tickers (list of strings)
    @property
    def tickers(self):
        """Get tickers as Python list"""
        if self._tickers:
            return json.loads(self._tickers)
        return []

    @tickers.setter
    def tickers(self, value):
        """Set tickers from Python list"""
        if value is None or value == []:
            self._tickers = None
        else:
            self._tickers = json.dumps(value)

    def __repr__(self):
        return f"<Technology(id={self.id}, name='{self.name}')>"
