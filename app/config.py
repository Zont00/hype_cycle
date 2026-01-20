from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/hype_cycle.db"

    # Semantic Scholar API
    semantic_scholar_api_key: Optional[str] = None
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"

    # PatentsView API
    patents_view_api_key: Optional[str] = None
    patents_view_base_url: str = "https://search.patentsview.org"

    # Reddit API
    reddit_base_url: str = "https://www.reddit.com"
    reddit_posts_limit: int = 250  # Total posts to collect
    reddit_batch_size: int = 100  # API max per request
    reddit_sort: str = "relevance"  # relevance, hot, top, new, comments

    # NewsAPI.org
    newsapi_api_key: Optional[str] = None
    newsapi_base_url: str = "https://newsapi.org"
    newsapi_page_size: int = 100  # Max per request
    newsapi_max_articles: int = 500  # Total articles to collect per technology
    newsapi_language: str = "en"
    newsapi_sort_by: str = "relevancy"  # relevancy, popularity, publishedAt
    newsapi_lookback_days: int = 30  # Free tier: max 30 days (paid plans: up to years)

    # Yahoo Finance (via yfinance - no API key required)
    finance_lookback_years: int = 10  # Historical data lookback period
    finance_frequency: str = "1mo"  # Data frequency: 1d (daily), 1wk (weekly), 1mo (monthly)
    finance_market_indices: str = '["^IXIC", "^GSPC"]'  # Market indices for comparison (NASDAQ, S&P500)
    finance_batch_delay_seconds: float = 0.5  # Delay between ticker requests for rate limiting

    # Collection parameters
    max_batches_per_collection: int = 10
    batch_size: int = 1000
    collection_timeout_seconds: int = 300

    # Time horizon
    paper_lookback_years: int = 10
    patent_lookback_years: int = 10

    # Patent collection parameters
    patents_batch_size: int = 1000  # PatentsView API max
    patents_rate_limit_requests: int = 45
    patents_rate_limit_window: int = 60  # seconds

    # API retry configuration
    max_retries: int = 3
    retry_delay_seconds: int = 2
    request_timeout_seconds: int = 30

    # Hype Cycle Analysis Configuration
    hype_cycle_velocity_growth_threshold: float = 20.0  # % increase = increasing trend
    hype_cycle_velocity_decline_threshold: float = -15.0  # % decrease = declining trend
    hype_cycle_citation_growth_high: float = 30.0  # % = rapid growth
    hype_cycle_citation_growth_moderate: float = 10.0  # % = moderate growth
    hype_cycle_basic_research_high: float = 70.0  # % = mostly basic science
    hype_cycle_applied_research_high: float = 60.0  # % = mostly applied
    hype_cycle_applied_research_very_high: float = 80.0  # % = overwhelmingly applied
    hype_cycle_min_papers_for_analysis: int = 100  # minimum papers needed
    hype_cycle_min_patents_for_analysis: int = 10  # minimum patents needed

    class Config:
        env_file = ".env"


settings = Settings()
