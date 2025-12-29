import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models import Technology, StockPrice, StockInfo

logger = logging.getLogger(__name__)


class YahooFinanceCollector:
    """Service for collecting stock market data from Yahoo Finance via yfinance library"""

    def __init__(self, db: Session):
        self.db = db
        self.lookback_years = settings.finance_lookback_years
        self.frequency = settings.finance_frequency
        self.market_indices = json.loads(settings.finance_market_indices)
        self.batch_delay = settings.finance_batch_delay_seconds
        self.timeout = settings.request_timeout_seconds

    async def collect_finance_data(self, technology_id: int) -> Dict:
        """
        Main collection method - orchestrates the entire collection process

        Args:
            technology_id: ID of the technology to collect finance data for

        Returns:
            Dict with collection statistics

        Raises:
            ValueError: If technology not found or not active
        """
        # Fetch technology
        technology = self.db.query(Technology).filter(Technology.id == technology_id).first()
        if not technology:
            raise ValueError(f"Technology with ID {technology_id} not found")

        if not technology.is_active:
            raise ValueError(f"Technology '{technology.name}' is not active")

        logger.info(f"Starting Yahoo Finance collection for technology '{technology.name}' (ID: {technology_id})")

        # Build ticker list: technology tickers + market indices
        tickers_to_collect = []
        if technology.tickers:
            tickers_to_collect.extend(technology.tickers)
            logger.info(f"Technology tickers: {technology.tickers}")

        # Add market indices
        tickers_to_collect.extend(self.market_indices)
        logger.info(f"Market indices: {self.market_indices}")

        # Deduplicate
        tickers_to_collect = list(set(tickers_to_collect))
        logger.info(f"Total unique tickers to process: {len(tickers_to_collect)}")

        # Collection stats
        stats = {
            "technology_id": technology_id,
            "technology_name": technology.name,
            "tickers_processed": 0,
            "prices_collected": 0,
            "new_prices": 0,
            "duplicate_prices": 0,
            "info_updated": 0,
            "errors": []
        }

        # Calculate date range (10 years back from today)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_years * 365)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(f"Date range: {start_date_str} to {end_date_str}")
        logger.info(f"Frequency: {self.frequency}")

        # Process each ticker
        for ticker in tickers_to_collect:
            try:
                logger.info(f"Processing ticker: {ticker}")

                # Fetch data from Yahoo Finance
                result = await self._fetch_ticker_data(ticker, start_date_str, end_date_str)

                if result is None:
                    logger.warning(f"No data retrieved for ticker: {ticker}")
                    stats["errors"].append(f"{ticker}: No data available")
                    continue

                hist_df, info_dict = result

                # Determine ticker type
                ticker_type = self._determine_ticker_type(ticker)

                # Save prices (time-series)
                if hist_df is not None and not hist_df.empty:
                    new_count, duplicate_count = self._save_prices(
                        ticker=ticker,
                        ticker_type=ticker_type,
                        df=hist_df,
                        technology_id=technology_id
                    )
                    stats["prices_collected"] += len(hist_df)
                    stats["new_prices"] += new_count
                    stats["duplicate_prices"] += duplicate_count
                    logger.info(f"{ticker}: {len(hist_df)} prices, {new_count} new, {duplicate_count} duplicates")
                else:
                    logger.warning(f"{ticker}: No historical price data available")

                # Save/update info (metadata/fundamentals)
                if info_dict is not None and info_dict:
                    updated = self._save_info(
                        ticker=ticker,
                        ticker_type=ticker_type,
                        info_dict=info_dict,
                        technology_id=technology_id
                    )
                    stats["info_updated"] += updated
                    logger.info(f"{ticker}: Info {'updated' if updated else 'not updated'}")
                else:
                    logger.warning(f"{ticker}: No fundamental data available")

                stats["tickers_processed"] += 1

                # Rate limiting: delay between requests
                await asyncio.sleep(self.batch_delay)

            except Exception as e:
                error_msg = f"{ticker}: {str(e)}"
                logger.error(f"Error processing ticker {ticker}: {str(e)}")
                stats["errors"].append(error_msg)
                continue

        logger.info(f"Collection completed: {stats['tickers_processed']} tickers processed, "
                   f"{stats['new_prices']} new prices, {stats['info_updated']} info updated")
        return stats

    async def _fetch_ticker_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[Tuple]:
        """
        Fetch data for a single ticker (async wrapper for sync yfinance)

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "^IXIC")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Tuple of (DataFrame history, Dict info) or None on error
        """
        try:
            # Run sync yfinance call in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._fetch_ticker_sync,
                ticker,
                start_date,
                end_date
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return None

    def _fetch_ticker_sync(self, ticker: str, start_date: str, end_date: str):
        """
        Synchronous yfinance call (executed in thread pool)

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Tuple of (DataFrame history, Dict info)
        """
        import yfinance as yf

        stock = yf.Ticker(ticker)

        # Fetch historical data
        hist = stock.history(start=start_date, end=end_date, interval=self.frequency)

        # Fetch company info / fundamentals
        try:
            info = stock.info
        except Exception as e:
            logger.warning(f"Could not fetch info for {ticker}: {str(e)}")
            info = {}

        return hist, info

    def _save_prices(
        self,
        ticker: str,
        ticker_type: str,
        df,
        technology_id: int
    ) -> Tuple[int, int]:
        """
        Save time-series OHLCV data to database

        Args:
            ticker: Stock ticker symbol
            ticker_type: "stock" or "index"
            df: Pandas DataFrame with OHLCV data
            technology_id: ID of the technology

        Returns:
            Tuple of (new_count, duplicate_count)
        """
        new_count = 0
        duplicate_count = 0

        for date_index, row in df.iterrows():
            try:
                # Extract date as string
                date_str = date_index.strftime("%Y-%m-%d")

                stock_price = StockPrice(
                    technology_id=technology_id,
                    ticker=ticker,
                    ticker_type=ticker_type,
                    date=date_str,
                    open=float(row.get("Open")) if "Open" in row and row.get("Open") is not None else None,
                    high=float(row.get("High")) if "High" in row and row.get("High") is not None else None,
                    low=float(row.get("Low")) if "Low" in row and row.get("Low") is not None else None,
                    close=float(row.get("Close")) if "Close" in row and row.get("Close") is not None else None,
                    adj_close=float(row.get("Close")) if "Close" in row and row.get("Close") is not None else None,
                    volume=int(row.get("Volume")) if "Volume" in row and row.get("Volume") is not None else None
                )

                self.db.add(stock_price)
                self.db.commit()
                new_count += 1

            except IntegrityError:
                # Duplicate (violates unique constraint on technology_id, ticker, date)
                self.db.rollback()
                duplicate_count += 1
                logger.debug(f"Duplicate price skipped: {ticker} on {date_str}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error saving price for {ticker} on {date_str}: {str(e)}")

        return new_count, duplicate_count

    def _save_info(
        self,
        ticker: str,
        ticker_type: str,
        info_dict: Dict,
        technology_id: int
    ) -> int:
        """
        Save/update ticker metadata and fundamentals (UPSERT pattern)

        Args:
            ticker: Stock ticker symbol
            ticker_type: "stock" or "index"
            info_dict: Dictionary with company info and fundamentals from yfinance
            technology_id: ID of the technology

        Returns:
            1 if saved/updated, 0 otherwise
        """
        try:
            # Check if info already exists
            existing_info = self.db.query(StockInfo).filter(
                StockInfo.technology_id == technology_id,
                StockInfo.ticker == ticker
            ).first()

            if existing_info:
                # Update existing record
                existing_info.ticker_type = ticker_type
                existing_info.company_name = info_dict.get("longName")
                existing_info.sector = info_dict.get("sector")
                existing_info.industry = info_dict.get("industry")
                existing_info.website = info_dict.get("website")
                existing_info.description = info_dict.get("longBusinessSummary")
                existing_info.country = info_dict.get("country")
                existing_info.market_cap = info_dict.get("marketCap")
                existing_info.pe_ratio = info_dict.get("trailingPE")
                existing_info.forward_pe = info_dict.get("forwardPE")
                existing_info.peg_ratio = info_dict.get("pegRatio")
                existing_info.price_to_book = info_dict.get("priceToBook")
                existing_info.dividend_yield = info_dict.get("dividendYield")
                existing_info.beta = info_dict.get("beta")
                existing_info.eps = info_dict.get("trailingEps")
                existing_info.revenue = info_dict.get("totalRevenue")
                existing_info.gross_profit = info_dict.get("grossProfits")

                self.db.commit()
                logger.debug(f"Updated info for ticker: {ticker}")
            else:
                # Create new record
                stock_info = StockInfo(
                    technology_id=technology_id,
                    ticker=ticker,
                    ticker_type=ticker_type,
                    company_name=info_dict.get("longName"),
                    sector=info_dict.get("sector"),
                    industry=info_dict.get("industry"),
                    website=info_dict.get("website"),
                    description=info_dict.get("longBusinessSummary"),
                    country=info_dict.get("country"),
                    market_cap=info_dict.get("marketCap"),
                    pe_ratio=info_dict.get("trailingPE"),
                    forward_pe=info_dict.get("forwardPE"),
                    peg_ratio=info_dict.get("pegRatio"),
                    price_to_book=info_dict.get("priceToBook"),
                    dividend_yield=info_dict.get("dividendYield"),
                    beta=info_dict.get("beta"),
                    eps=info_dict.get("trailingEps"),
                    revenue=info_dict.get("totalRevenue"),
                    gross_profit=info_dict.get("grossProfits")
                )

                self.db.add(stock_info)
                self.db.commit()
                logger.debug(f"Created info for ticker: {ticker}")

            return 1

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving info for {ticker}: {str(e)}")
            return 0

    def _determine_ticker_type(self, ticker: str) -> str:
        """
        Determine if ticker is a stock or market index

        Args:
            ticker: Stock ticker symbol

        Returns:
            "index" if ticker starts with "^", otherwise "stock"
        """
        return "index" if ticker.startswith("^") else "stock"
