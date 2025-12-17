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

    class Config:
        env_file = ".env"


settings = Settings()
