from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from collections import defaultdict
import numpy as np
import logging

from ..models import StockPrice, StockInfo

logger = logging.getLogger(__name__)


@dataclass
class FinanceMetricsSnapshot:
    """Snapshot of all calculated Finance metrics"""
    # Overview
    tickers_analyzed: List[str]
    total_price_records: int
    date_range_start: str
    date_range_end: str

    # Price metrics (aggregated across all tickers)
    avg_daily_return: float  # percentage
    total_return: float  # percentage over entire period
    volatility: float  # standard deviation of daily returns
    max_drawdown: float  # maximum peak-to-trough decline percentage
    sharpe_ratio: float  # risk-adjusted return (assuming 0% risk-free rate)

    # Price trend
    price_trend: str  # "bullish", "bearish", "sideways"
    price_change_last_month: float  # percentage
    price_change_last_3_months: float  # percentage

    # Volume metrics
    avg_daily_volume: float
    volume_trend: str  # "increasing", "decreasing", "stable"
    volume_change_percentage: float  # recent vs earlier

    # Per-ticker breakdown
    ticker_performance: Dict[str, Dict]  # ticker -> {return, volatility, etc.}

    # Fundamental metrics (from StockInfo, if available)
    avg_pe_ratio: Optional[float]
    avg_market_cap: Optional[float]
    sectors_represented: List[str]
    industries_represented: List[str]

    # Correlation metrics
    avg_correlation_between_tickers: Optional[float]

    # Data quality
    records_with_volume: int
    coverage_percentage: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class FinanceMetricsCalculator:
    """Calculate metrics from Finance data for Hype Cycle analysis"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, technology_id: int) -> FinanceMetricsSnapshot:
        """
        Calculate all metrics for a technology's financial data

        Args:
            technology_id: ID of technology to analyze

        Returns:
            FinanceMetricsSnapshot with all calculated metrics
        """
        logger.info(f"Starting Finance metrics calculation for technology {technology_id}")

        # Fetch all price data for this technology
        prices = self.db.query(StockPrice)\
            .filter(StockPrice.technology_id == technology_id)\
            .order_by(StockPrice.ticker, StockPrice.date)\
            .all()

        if not prices:
            raise ValueError(f"No stock price data found for technology {technology_id}")

        if len(prices) < 20:
            raise ValueError(f"Insufficient price data for analysis. Found {len(prices)}, need at least 20.")

        # Fetch stock info
        stock_info = self.db.query(StockInfo)\
            .filter(StockInfo.technology_id == technology_id)\
            .all()

        logger.info(f"Found {len(prices)} price records and {len(stock_info)} stock info records")

        # Group prices by ticker
        prices_by_ticker = defaultdict(list)
        for price in prices:
            prices_by_ticker[price.ticker].append(price)

        # Sort each ticker's prices by date
        for ticker in prices_by_ticker:
            prices_by_ticker[ticker].sort(key=lambda p: p.date)

        # Calculate each metric category
        overview_metrics = self._calculate_overview_metrics(prices, prices_by_ticker)
        price_metrics = self._calculate_price_metrics(prices_by_ticker)
        volume_metrics = self._calculate_volume_metrics(prices_by_ticker)
        ticker_breakdown = self._calculate_ticker_breakdown(prices_by_ticker)
        fundamental_metrics = self._calculate_fundamental_metrics(stock_info)
        correlation_metrics = self._calculate_correlation_metrics(prices_by_ticker)
        quality_metrics = self._calculate_quality_metrics(prices)

        # Combine into snapshot
        metrics = FinanceMetricsSnapshot(
            **overview_metrics,
            **price_metrics,
            **volume_metrics,
            ticker_performance=ticker_breakdown,
            **fundamental_metrics,
            **correlation_metrics,
            **quality_metrics
        )

        logger.info("Finance metrics calculation completed")
        return metrics

    def _calculate_overview_metrics(self, prices: List[StockPrice], prices_by_ticker: Dict) -> Dict:
        """Calculate overview metrics"""
        logger.info("Calculating Finance overview metrics...")

        tickers = list(prices_by_ticker.keys())
        dates = [p.date for p in prices if p.date]

        if dates:
            date_range_start = min(dates)
            date_range_end = max(dates)
        else:
            date_range_start = "unknown"
            date_range_end = "unknown"

        return {
            "tickers_analyzed": tickers,
            "total_price_records": len(prices),
            "date_range_start": date_range_start,
            "date_range_end": date_range_end
        }

    def _calculate_price_metrics(self, prices_by_ticker: Dict) -> Dict:
        """Calculate price-related metrics"""
        logger.info("Calculating Finance price metrics...")

        all_daily_returns = []
        all_total_returns = []
        all_prices_series = []

        for ticker, ticker_prices in prices_by_ticker.items():
            if len(ticker_prices) < 2:
                continue

            # Get adjusted close prices
            adj_closes = [p.adj_close or p.close for p in ticker_prices if (p.adj_close or p.close)]

            if len(adj_closes) < 2:
                continue

            # Calculate daily returns
            returns = []
            for i in range(1, len(adj_closes)):
                if adj_closes[i-1] > 0:
                    daily_return = (adj_closes[i] - adj_closes[i-1]) / adj_closes[i-1]
                    returns.append(daily_return)

            if returns:
                all_daily_returns.extend(returns)

            # Calculate total return
            if adj_closes[0] > 0:
                total_return = (adj_closes[-1] - adj_closes[0]) / adj_closes[0]
                all_total_returns.append(total_return)

            all_prices_series.append(adj_closes)

        # Aggregate metrics
        if all_daily_returns:
            avg_daily_return = np.mean(all_daily_returns) * 100
            volatility = np.std(all_daily_returns) * 100

            # Sharpe ratio (annualized, assuming 0% risk-free rate)
            if volatility > 0:
                sharpe_ratio = (avg_daily_return * 252) / (volatility * np.sqrt(252))
            else:
                sharpe_ratio = 0.0
        else:
            avg_daily_return = 0.0
            volatility = 0.0
            sharpe_ratio = 0.0

        if all_total_returns:
            total_return = np.mean(all_total_returns) * 100
        else:
            total_return = 0.0

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(all_prices_series)

        # Price trend and recent changes
        price_trend, price_change_1m, price_change_3m = self._calculate_price_trend(prices_by_ticker)

        return {
            "avg_daily_return": avg_daily_return,
            "total_return": total_return,
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "price_trend": price_trend,
            "price_change_last_month": price_change_1m,
            "price_change_last_3_months": price_change_3m
        }

    def _calculate_max_drawdown(self, price_series_list: List[List[float]]) -> float:
        """Calculate maximum drawdown across all price series"""
        max_drawdowns = []

        for prices in price_series_list:
            if len(prices) < 2:
                continue

            peak = prices[0]
            max_dd = 0.0

            for price in prices:
                if price > peak:
                    peak = price
                drawdown = (peak - price) / peak if peak > 0 else 0
                max_dd = max(max_dd, drawdown)

            max_drawdowns.append(max_dd)

        if max_drawdowns:
            return np.mean(max_drawdowns) * 100
        return 0.0

    def _calculate_price_trend(self, prices_by_ticker: Dict) -> Tuple[str, float, float]:
        """Calculate price trend and recent changes"""
        changes_1m = []
        changes_3m = []

        for ticker, ticker_prices in prices_by_ticker.items():
            if len(ticker_prices) < 5:
                continue

            # Get dates and prices
            date_prices = [(p.date, p.adj_close or p.close) for p in ticker_prices if p.date and (p.adj_close or p.close)]
            date_prices.sort(key=lambda x: x[0])

            if not date_prices:
                continue

            # Last price
            last_price = date_prices[-1][1]
            last_date = datetime.strptime(date_prices[-1][0], "%Y-%m-%d")

            # Find price ~1 month ago (approx 21 trading days)
            idx_1m = max(0, len(date_prices) - 21)
            price_1m_ago = date_prices[idx_1m][1]
            if price_1m_ago > 0:
                changes_1m.append((last_price - price_1m_ago) / price_1m_ago * 100)

            # Find price ~3 months ago (approx 63 trading days)
            idx_3m = max(0, len(date_prices) - 63)
            price_3m_ago = date_prices[idx_3m][1]
            if price_3m_ago > 0:
                changes_3m.append((last_price - price_3m_ago) / price_3m_ago * 100)

        # Calculate averages
        price_change_1m = np.mean(changes_1m) if changes_1m else 0.0
        price_change_3m = np.mean(changes_3m) if changes_3m else 0.0

        # Determine trend
        if price_change_3m > 10:
            trend = "bullish"
        elif price_change_3m < -10:
            trend = "bearish"
        else:
            trend = "sideways"

        return trend, price_change_1m, price_change_3m

    def _calculate_volume_metrics(self, prices_by_ticker: Dict) -> Dict:
        """Calculate volume-related metrics"""
        logger.info("Calculating Finance volume metrics...")

        all_volumes = []
        early_volumes = []
        recent_volumes = []

        for ticker, ticker_prices in prices_by_ticker.items():
            volumes = [p.volume for p in ticker_prices if p.volume and p.volume > 0]

            if volumes:
                all_volumes.extend(volumes)

                # Split into early and recent
                midpoint = len(volumes) // 2
                early_volumes.extend(volumes[:midpoint])
                recent_volumes.extend(volumes[midpoint:])

        # Calculate metrics
        avg_daily_volume = np.mean(all_volumes) if all_volumes else 0.0

        # Volume trend
        if early_volumes and recent_volumes:
            early_avg = np.mean(early_volumes)
            recent_avg = np.mean(recent_volumes)

            if early_avg > 0:
                volume_change = ((recent_avg - early_avg) / early_avg) * 100
            else:
                volume_change = 0.0

            if volume_change > 20:
                volume_trend = "increasing"
            elif volume_change < -20:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"
        else:
            volume_trend = "insufficient_data"
            volume_change = 0.0

        return {
            "avg_daily_volume": avg_daily_volume,
            "volume_trend": volume_trend,
            "volume_change_percentage": volume_change
        }

    def _calculate_ticker_breakdown(self, prices_by_ticker: Dict) -> Dict[str, Dict]:
        """Calculate per-ticker performance metrics"""
        logger.info("Calculating Finance ticker breakdown...")

        ticker_performance = {}

        for ticker, ticker_prices in prices_by_ticker.items():
            if len(ticker_prices) < 2:
                continue

            adj_closes = [p.adj_close or p.close for p in ticker_prices if (p.adj_close or p.close)]

            if len(adj_closes) < 2:
                continue

            # Calculate returns
            returns = []
            for i in range(1, len(adj_closes)):
                if adj_closes[i-1] > 0:
                    daily_return = (adj_closes[i] - adj_closes[i-1]) / adj_closes[i-1]
                    returns.append(daily_return)

            if returns:
                total_return = (adj_closes[-1] - adj_closes[0]) / adj_closes[0] * 100 if adj_closes[0] > 0 else 0
                avg_return = np.mean(returns) * 100
                volatility = np.std(returns) * 100

                ticker_performance[ticker] = {
                    "total_return_pct": round(total_return, 2),
                    "avg_daily_return_pct": round(avg_return, 4),
                    "volatility_pct": round(volatility, 2),
                    "num_records": len(ticker_prices),
                    "latest_price": adj_closes[-1] if adj_closes else None
                }

        return ticker_performance

    def _calculate_fundamental_metrics(self, stock_info: List[StockInfo]) -> Dict:
        """Calculate fundamental metrics from stock info"""
        logger.info("Calculating Finance fundamental metrics...")

        if not stock_info:
            return {
                "avg_pe_ratio": None,
                "avg_market_cap": None,
                "sectors_represented": [],
                "industries_represented": []
            }

        pe_ratios = [s.pe_ratio for s in stock_info if s.pe_ratio and s.pe_ratio > 0]
        market_caps = [s.market_cap for s in stock_info if s.market_cap and s.market_cap > 0]
        sectors = list(set(s.sector for s in stock_info if s.sector))
        industries = list(set(s.industry for s in stock_info if s.industry))

        return {
            "avg_pe_ratio": np.mean(pe_ratios) if pe_ratios else None,
            "avg_market_cap": np.mean(market_caps) if market_caps else None,
            "sectors_represented": sectors,
            "industries_represented": industries
        }

    def _calculate_correlation_metrics(self, prices_by_ticker: Dict) -> Dict:
        """Calculate correlation between tickers"""
        logger.info("Calculating Finance correlation metrics...")

        if len(prices_by_ticker) < 2:
            return {"avg_correlation_between_tickers": None}

        # Build return series aligned by date
        ticker_returns = {}

        for ticker, ticker_prices in prices_by_ticker.items():
            returns_by_date = {}
            sorted_prices = sorted(ticker_prices, key=lambda p: p.date)

            for i in range(1, len(sorted_prices)):
                prev_price = sorted_prices[i-1].adj_close or sorted_prices[i-1].close
                curr_price = sorted_prices[i].adj_close or sorted_prices[i].close

                if prev_price and curr_price and prev_price > 0:
                    daily_return = (curr_price - prev_price) / prev_price
                    returns_by_date[sorted_prices[i].date] = daily_return

            if returns_by_date:
                ticker_returns[ticker] = returns_by_date

        # Calculate pairwise correlations
        correlations = []
        tickers = list(ticker_returns.keys())

        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                ticker1 = tickers[i]
                ticker2 = tickers[j]

                # Find common dates
                common_dates = set(ticker_returns[ticker1].keys()) & set(ticker_returns[ticker2].keys())

                if len(common_dates) >= 20:
                    returns1 = [ticker_returns[ticker1][d] for d in common_dates]
                    returns2 = [ticker_returns[ticker2][d] for d in common_dates]

                    corr = np.corrcoef(returns1, returns2)[0, 1]
                    if not np.isnan(corr):
                        correlations.append(corr)

        avg_correlation = np.mean(correlations) if correlations else None

        return {"avg_correlation_between_tickers": avg_correlation}

    def _calculate_quality_metrics(self, prices: List[StockPrice]) -> Dict:
        """Calculate data quality metrics"""
        logger.info("Calculating Finance data quality metrics...")

        total = len(prices)
        with_volume = sum(1 for p in prices if p.volume and p.volume > 0)
        coverage = (with_volume / total) * 100 if total > 0 else 0

        return {
            "records_with_volume": with_volume,
            "coverage_percentage": coverage
        }
