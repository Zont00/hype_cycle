from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

from ..database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Semantic Scholar fields - Basic
    paper_id = Column(String(40), nullable=False, index=True)
    title = Column(Text, nullable=False)
    year = Column(Integer, nullable=True)
    citation_count = Column(Integer, nullable=True, default=0)
    publication_date = Column(String(10), nullable=True)  # YYYY-MM-DD format

    # Semantic Scholar fields - Extended
    abstract = Column(Text, nullable=True)
    _authors = Column("authors", Text, nullable=True)  # JSON list
    venue = Column(String(500), nullable=True)
    _s2_fields_of_study = Column("s2_fields_of_study", Text, nullable=True)  # JSON list
    open_access_pdf = Column(String(1000), nullable=True)  # URL

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="papers")

    # Composite unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_tech_paper', 'technology_id', 'paper_id', unique=True),
    )

    # Property methods for authors (list of dicts)
    @property
    def authors(self):
        """Get authors as Python list"""
        if self._authors:
            return json.loads(self._authors)
        return []

    @authors.setter
    def authors(self, value):
        """Set authors from Python list"""
        if value is None or value == []:
            self._authors = None
        else:
            self._authors = json.dumps(value)

    # Property methods for s2_fields_of_study (list of dicts)
    @property
    def s2_fields_of_study(self):
        """Get fields of study as Python list"""
        if self._s2_fields_of_study:
            return json.loads(self._s2_fields_of_study)
        return []

    @s2_fields_of_study.setter
    def s2_fields_of_study(self, value):
        """Set fields of study from Python list"""
        if value is None or value == []:
            self._s2_fields_of_study = None
        else:
            self._s2_fields_of_study = json.dumps(value)

    def __repr__(self):
        return f"<Paper(id={self.id}, paper_id='{self.paper_id}', title='{self.title[:50]}...')>"
