from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/hype_cycle.db"

    # Semantic Scholar API
    semantic_scholar_api_key: Optional[str] = None
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"

    # Collection parameters
    max_batches_per_collection: int = 10
    batch_size: int = 1000
    collection_timeout_seconds: int = 300

    # Time horizon
    paper_lookback_years: int = 10

    # API retry configuration
    max_retries: int = 3
    retry_delay_seconds: int = 2
    request_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
