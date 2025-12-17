from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

from ..database import Base


class Patent(Base):
    __tablename__ = "patents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # PatentsView fields - Basic
    patent_id = Column(String(20), nullable=False, index=True)  # US patent number
    patent_title = Column(Text, nullable=False)
    patent_abstract = Column(Text, nullable=True)
    patent_date = Column(String(10), nullable=True)  # YYYY-MM-DD format
    patent_year = Column(Integer, nullable=True, index=True)  # For efficient querying
    patent_type = Column(String(50), nullable=True)  # e.g., "utility", "design"

    # Citation metrics (key for Hype Cycle analysis)
    patent_num_us_patents_cited = Column(Integer, nullable=True, default=0)
    patent_num_times_cited_by_us_patents = Column(Integer, nullable=True, default=0)

    # Assignee data (JSON)
    _assignees = Column("assignees", Text, nullable=True)  # JSON list of assignee objects

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="patents")

    # Composite unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_tech_patent', 'technology_id', 'patent_id', unique=True),
    )

    # Property methods for assignees (list of dicts)
    @property
    def assignees(self):
        """Get assignees as Python list"""
        if self._assignees:
            return json.loads(self._assignees)
        return []

    @assignees.setter
    def assignees(self, value):
        """Set assignees from Python list"""
        if value is None or value == []:
            self._assignees = None
        else:
            self._assignees = json.dumps(value)

    def __repr__(self):
        return f"<Patent(id={self.id}, patent_id='{self.patent_id}', title='{self.patent_title[:50]}...')>"
