from sqlalchemy import Column, Integer, String, Text, Float, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class StockInfo(Base):
    __tablename__ = "stock_info"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Ticker identifiers
    ticker = Column(String(20), nullable=False, index=True)
    ticker_type = Column(String(10), nullable=False)  # "stock" or "index"

    # Company information (static metadata)
    company_name = Column(String(500), nullable=True)
    sector = Column(String(200), nullable=True)
    industry = Column(String(200), nullable=True)
    website = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)

    # Fundamentals (current snapshot - updated on each collection)
    market_cap = Column(BigInteger, nullable=True)
    pe_ratio = Column(Float, nullable=True)  # Price-to-Earnings (trailing)
    forward_pe = Column(Float, nullable=True)  # Forward P/E
    peg_ratio = Column(Float, nullable=True)  # Price/Earnings to Growth
    price_to_book = Column(Float, nullable=True)  # Price-to-Book ratio
    dividend_yield = Column(Float, nullable=True)  # Dividend yield (percentage)
    beta = Column(Float, nullable=True)  # Volatility vs market
    eps = Column(Float, nullable=True)  # Earnings per share (trailing)
    revenue = Column(BigInteger, nullable=True)  # Total revenue
    gross_profit = Column(BigInteger, nullable=True)  # Gross profit

    # Timestamps
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="stock_info")

    # Composite unique constraint (one info record per ticker per technology)
    __table_args__ = (
        Index('idx_tech_ticker_info', 'technology_id', 'ticker', unique=True),
    )

    def __repr__(self):
        return f"<StockInfo(id={self.id}, ticker='{self.ticker}', company='{self.company_name}')>"
