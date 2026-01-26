from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class FinanceAnalysisResponse(BaseModel):
    """Response schema for Finance analysis"""
    technology_id: int
    analysis_date: datetime
    total_price_records: int

    # Phase determination
    current_phase: str
    phase_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    phase_scores: Optional[Dict[str, float]] = None
    rationale: Optional[str] = None

    # Overview
    tickers_analyzed: List[str]
    date_range_start: str
    date_range_end: str

    # Price metrics
    avg_daily_return: float
    total_return: float
    volatility: float
    max_drawdown: float
    sharpe_ratio: float

    # Price trend
    price_trend: str
    price_change_last_month: float
    price_change_last_3_months: float

    # Volume metrics
    avg_daily_volume: float
    volume_trend: str
    volume_change_percentage: float

    # Per-ticker breakdown
    ticker_performance: Dict[str, Dict[str, Any]]

    # Fundamental metrics
    avg_pe_ratio: Optional[float] = None
    avg_market_cap: Optional[float] = None
    sectors_represented: List[str]
    industries_represented: List[str]

    # Correlation metrics
    avg_correlation_between_tickers: Optional[float] = None

    # Data quality
    records_with_volume: int
    coverage_percentage: float

    class Config:
        from_attributes = True
