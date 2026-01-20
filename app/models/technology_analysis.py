from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

from ..database import Base


class TechnologyAnalysis(Base):
    """Stores Hype Cycle analysis results for a technology"""
    __tablename__ = "technology_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    technology_id = Column(
        Integer,
        ForeignKey("technologies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Current phase determination
    current_phase = Column(String(50), nullable=False)  # HypeCyclePhase enum value
    phase_confidence = Column(Float, nullable=False)  # 0.0-1.0

    # Analysis metadata
    analysis_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_papers_analyzed = Column(Integer, nullable=False)
    date_range_start = Column(String(10), nullable=True)  # YYYY-MM-DD
    date_range_end = Column(String(10), nullable=True)    # YYYY-MM-DD

    # Core metrics (JSON serialized for flexibility)
    _metrics = Column("metrics", Text, nullable=False)  # Will store MetricsSnapshot as JSON

    # Patent metrics (JSON serialized)
    _patent_metrics = Column("patent_metrics", Text, nullable=True)  # Will store PatentMetricsSnapshot as JSON
    patent_analysis_date = Column(DateTime(timezone=True), nullable=True)

    # Rule evaluation results
    _rule_scores = Column("rule_scores", Text, nullable=True)  # Dict of rule -> score

    # Phase determination rationale
    rationale = Column(Text, nullable=True)  # Explanation of why this phase was chosen

    # Relationships
    technology = relationship("Technology", back_populates="analysis")

    @property
    def metrics(self):
        """Get metrics as Python dict"""
        if self._metrics:
            return json.loads(self._metrics)
        return {}

    @metrics.setter
    def metrics(self, value):
        """Set metrics from Python dict"""
        if value:
            self._metrics = json.dumps(value)
        else:
            self._metrics = "{}"

    @property
    def rule_scores(self):
        """Get rule scores as Python dict"""
        if self._rule_scores:
            return json.loads(self._rule_scores)
        return {}

    @rule_scores.setter
    def rule_scores(self, value):
        """Set rule scores from Python dict"""
        if value:
            self._rule_scores = json.dumps(value)
        else:
            self._rule_scores = None

    @property
    def patent_metrics(self):
        """Get patent metrics as Python dict"""
        if self._patent_metrics:
            return json.loads(self._patent_metrics)
        return {}

    @patent_metrics.setter
    def patent_metrics(self, value):
        """Set patent metrics from Python dict"""
        if value:
            self._patent_metrics = json.dumps(value)
        else:
            self._patent_metrics = None

    def __repr__(self):
        return f"<TechnologyAnalysis(id={self.id}, technology_id={self.technology_id}, phase='{self.current_phase}')>"
