from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# Stock Price Schemas
class StockPriceBase(BaseModel):
    ticker: str
    ticker_type: str
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adj_close: Optional[float] = None
    volume: Optional[int] = None


class StockPriceResponse(StockPriceBase):
    id: int
    technology_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Stock Info Schemas
class StockInfoBase(BaseModel):
    ticker: str
    ticker_type: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    eps: Optional[float] = None
    revenue: Optional[int] = None
    gross_profit: Optional[int] = None


class StockInfoResponse(StockInfoBase):
    id: int
    technology_id: int
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# Collection Stats Schema
class FinanceCollectionStats(BaseModel):
    technology_id: int
    technology_name: str
    tickers_processed: int
    prices_collected: int
    new_prices: int
    duplicate_prices: int
    info_updated: int
    errors: List[str]
