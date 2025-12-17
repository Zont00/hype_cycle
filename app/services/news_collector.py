import httpx
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models import Technology, NewsArticle

logger = logging.getLogger(__name__)


class NewsCollector:
    """Service for collecting news articles from NewsAPI.org"""

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.newsapi_base_url
        self.api_key = settings.newsapi_api_key
        self.page_size = settings.newsapi_page_size
        self.max_articles = settings.newsapi_max_articles
        self.language = settings.newsapi_language
        self.sort_by = settings.newsapi_sort_by
        self.timeout = settings.request_timeout_seconds

    def build_query(self, technology: Technology) -> str:
        """
        Build NewsAPI query from technology keywords and excluded terms

        Format: ("keyword1" OR "keyword2") AND NOT ("excluded1" OR "excluded2")

        NewsAPI supports:
        - OR operator for alternatives
        - AND for required terms
        - NOT for exclusions
        - Quotes for exact phrases
        - Parentheses for grouping

        Args:
            technology: Technology object with keywords and excluded_terms

        Returns:
            Formatted query string (max 500 chars)
        """
        # Quote each keyword and join with OR operator
        keyword_parts = [f'"{kw}"' for kw in technology.keywords]
        query = f"({' OR '.join(keyword_parts)})"

        # Add excluded terms with NOT operator
        if technology.excluded_terms:
            excluded_parts = [f'"{term}"' for term in technology.excluded_terms]
            query = f"{query} AND NOT ({' OR '.join(excluded_parts)})"

        # Ensure query doesn't exceed 500 chars (NewsAPI limit)
        if len(query) > 500:
            logger.warning(f"Query length ({len(query)}) exceeds 500 chars, truncating...")
            query = query[:497] + "..."

        return query

    def get_date_range(self) -> Tuple[str, str]:
        """
        Calculate date range for news collection

        Free tier: last 30 days max
        Paid plans: can go back further

        Returns:
            Tuple of (from_date, to_date) in YYYY-MM-DD format
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=settings.newsapi_lookback_days)

        # NewsAPI accepts ISO 8601: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        # Using simplified format for clarity
        return (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    def _generate_article_id(self, article: Dict) -> str:
        """
        Generate unique article ID from URL

        NewsAPI doesn't provide unique IDs, so we create one using MD5 hash of URL

        Args:
            article: Article dictionary from API

        Returns:
            MD5 hash of the article URL
        """
        url = article.get("url", "")
        return hashlib.md5(url.encode()).hexdigest()

    async def collect_articles(self, technology_id: int) -> Dict:
        """
        Main collection method - orchestrates the entire collection process

        Args:
            technology_id: ID of the technology to collect articles for

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

        # Build query
        query = self.build_query(technology)
        from_date, to_date = self.get_date_range()

        logger.info(f"Starting news collection for technology '{technology.name}' (ID: {technology_id})")
        logger.info(f"Query: {query}")
        logger.info(f"Date range: {from_date} to {to_date}")

        # Collection stats
        stats = {
            "technology_id": technology_id,
            "technology_name": technology.name,
            "articles_collected": 0,
            "total_articles_found": 0,
            "batches_processed": 0,
            "new_articles": 0,
            "duplicate_articles": 0,
            "errors": []
        }

        # Pagination (NewsAPI uses page numbers, starting at 1)
        page = 1
        total_collected = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while total_collected < self.max_articles:
                try:
                    # Fetch batch
                    result = await self._fetch_batch(
                        client=client,
                        query=query,
                        from_date=from_date,
                        to_date=to_date,
                        page=page
                    )

                    if result is None:
                        break  # API error, stop collection

                    total, articles = result

                    # First batch - record total
                    if page == 1:
                        stats["total_articles_found"] = total
                        logger.info(f"Total articles found: {total}")

                    # No more articles
                    if not articles:
                        logger.info("No more articles available")
                        break

                    # Save articles to database
                    new_count, duplicate_count = self._save_articles(
                        articles=articles,
                        technology_id=technology_id
                    )

                    stats["new_articles"] += new_count
                    stats["duplicate_articles"] += duplicate_count
                    stats["articles_collected"] += len(articles)
                    stats["batches_processed"] += 1
                    total_collected += len(articles)

                    logger.info(f"Page {page}: {len(articles)} articles, {new_count} new, {duplicate_count} duplicates")

                    # Check if we've reached the limit or no more pages
                    if len(articles) < self.page_size:
                        logger.info("Reached last page (fewer articles than page size)")
                        break

                    page += 1

                except Exception as e:
                    error_msg = f"Error on page {page}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    break

        logger.info(f"Collection completed: {stats['new_articles']} new articles, {stats['duplicate_articles']} duplicates")
        return stats

    async def _fetch_batch(
        self,
        client: httpx.AsyncClient,
        query: str,
        from_date: str,
        to_date: str,
        page: int
    ) -> Optional[Tuple[int, List[Dict]]]:
        """
        Fetch a single batch from NewsAPI /v2/everything endpoint

        Args:
            client: httpx AsyncClient instance
            query: Search query string
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            page: Page number (1-indexed)

        Returns:
            Tuple of (total_count, articles_list) or None on error
        """
        url = f"{self.base_url}/v2/everything"

        params = {
            "q": query,
            "from": from_date,
            "to": to_date,
            "language": self.language,
            "sortBy": self.sort_by,
            "pageSize": self.page_size,
            "page": page
        }

        headers = {
            "X-Api-Key": self.api_key
        }

        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # NewsAPI response: {"status": "ok", "totalResults": X, "articles": [...]}
            # or {"status": "error", "code": "...", "message": "..."}
            if data.get("status") != "ok":
                error_code = data.get("code", "unknown")
                error_message = data.get("message", "Unknown error")
                logger.error(f"API error: {error_code} - {error_message}")
                return None

            return (
                data.get("totalResults", 0),
                data.get("articles", [])
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            # Check for rate limiting (426 Too Many Requests or 429)
            if e.response.status_code in [426, 429]:
                logger.error("Rate limit exceeded - NewsAPI free tier: 100 requests/day")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None

    def _save_articles(
        self,
        articles: List[Dict],
        technology_id: int
    ) -> Tuple[int, int]:
        """
        Save articles to database with duplicate detection

        Args:
            articles: List of article dictionaries from API
            technology_id: ID of the technology

        Returns:
            Tuple of (new_count, duplicate_count)
        """
        new_count = 0
        duplicate_count = 0

        for article_data in articles:
            try:
                # Generate unique ID from URL
                article_id = self._generate_article_id(article_data)

                article = NewsArticle(
                    technology_id=technology_id,
                    article_id=article_id,
                    title=article_data.get("title", ""),
                    description=article_data.get("description"),
                    content=article_data.get("content"),
                    url=article_data.get("url", ""),
                    url_to_image=article_data.get("urlToImage"),
                    published_at=article_data.get("publishedAt"),
                    author=article_data.get("author")
                )

                # Handle source object using property
                article.source = article_data.get("source", {})

                self.db.add(article)
                self.db.commit()
                new_count += 1

            except IntegrityError:
                # Duplicate article (violates unique constraint)
                self.db.rollback()
                duplicate_count += 1
                logger.debug(f"Duplicate article skipped: {article_data.get('url')}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error saving article {article_data.get('url')}: {str(e)}")

        return new_count, duplicate_count
