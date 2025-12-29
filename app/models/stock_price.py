from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to Technology
    technology_id = Column(Integer, ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Ticker identifiers
    ticker = Column(String(20), nullable=False, index=True)  # e.g., "AAPL", "^IXIC"
    ticker_type = Column(String(10), nullable=False)  # "stock" or "index"
    date = Column(String(10), nullable=False, index=True)  # "YYYY-MM-DD"

    # OHLCV data (nullable as some data might be missing)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)  # Adjusted close (accounts for splits/dividends)
    volume = Column(BigInteger, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship to Technology
    technology = relationship("Technology", back_populates="stock_prices")

    # Composite unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_tech_ticker_date', 'technology_id', 'ticker', 'date', unique=True),
    )

    def __repr__(self):
        return f"<StockPrice(id={self.id}, ticker='{self.ticker}', date='{self.date}', close={self.close})>"
