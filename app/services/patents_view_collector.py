import httpx
import logging
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models import Technology, Patent

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for PatentsView API (45 requests/minute)"""

    def __init__(self, max_requests: int = 45, time_window: int = 60):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, wait if necessary"""
        async with self.lock:
            now = datetime.now()
            elapsed = (now - self.last_update).total_seconds()

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.max_requests,
                self.tokens + (elapsed * self.max_requests / self.time_window)
            )
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * self.time_window / self.max_requests
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 1

            self.tokens -= 1


class PatentsViewCollector:
    """Service for collecting patents from PatentsView API"""

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.patents_view_base_url
        self.api_key = settings.patents_view_api_key
        self.batch_size = settings.patents_batch_size
        self.timeout = settings.request_timeout_seconds
        self.rate_limiter = RateLimiter(
            max_requests=settings.patents_rate_limit_requests,
            time_window=settings.patents_rate_limit_window
        )

    def build_query(self, technology: Technology) -> Dict:
        """
        Build PatentsView JSON query from technology keywords and excluded terms

        Query structure:
        - Use _or array with each keyword searched in both title and abstract using _text_all
        - Patent matches if it contains AT LEAST ONE keyword
        - Use _not with _or array for excluded terms
        - Patent is excluded if it contains ANY excluded term

        Args:
            technology: Technology object with keywords and excluded_terms

        Returns:
            Dict representing the JSON query structure
        """
        # Get year range
        start_year, end_year = self.get_year_range()

        # Build keyword OR conditions (search in both title and abstract)
        keyword_conditions = []
        for keyword in technology.keywords:
            keyword_conditions.append({"_text_all": {"patent_title": keyword}})
            keyword_conditions.append({"_text_all": {"patent_abstract": keyword}})

        # Build base query with keywords and date range
        query = {
            "_and": [
                {"_or": keyword_conditions},
                {"_gte": {"patent_year": start_year}},
                {"_lte": {"patent_year": end_year}}
            ]
        }

        # Add excluded terms if present
        if technology.excluded_terms:
            excluded_conditions = []
            for excluded_term in technology.excluded_terms:
                excluded_conditions.append({"_text_all": {"patent_title": excluded_term}})
                excluded_conditions.append({"_text_all": {"patent_abstract": excluded_term}})

            query["_and"].append({
                "_not": {
                    "_or": excluded_conditions
                }
            })

        return query

    def get_year_range(self) -> Tuple[int, int]:
        """
        Calculate year range for patent collection

        Returns:
            Tuple of (start_year, end_year)
        """
        end_year = datetime.now().year
        start_year = end_year - settings.patent_lookback_years
        return (start_year, end_year)

    async def collect_patents(self, technology_id: int) -> Dict:
        """
        Main collection method - orchestrates the entire collection process

        Args:
            technology_id: ID of the technology to collect patents for

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
        start_year, end_year = self.get_year_range()

        logger.info(f"Starting patent collection for technology '{technology.name}' (ID: {technology_id})")
        logger.info(f"Query: {json.dumps(query)}")
        logger.info(f"Year range: {start_year} to {end_year}")

        # Collection stats
        stats = {
            "technology_id": technology_id,
            "technology_name": technology.name,
            "patents_collected": 0,
            "total_patents_found": 0,
            "batches_processed": 0,
            "new_patents": 0,
            "duplicate_patents": 0,
            "errors": []
        }

        # Cursor pagination
        cursor = None
        batch_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:  # Collect all patents
                try:
                    # Apply rate limiting
                    await self.rate_limiter.acquire()

                    # Fetch batch
                    result = await self._fetch_batch(
                        client=client,
                        query=query,
                        cursor=cursor
                    )

                    if result is None:
                        break  # API error, stop collection

                    total, patents, next_cursor = result

                    # First batch - record total
                    if batch_count == 0:
                        stats["total_patents_found"] = total
                        logger.info(f"Total patents found: {total}")

                    # Save patents to database
                    new_count, duplicate_count = self._save_patents(
                        patents=patents,
                        technology_id=technology_id
                    )

                    stats["new_patents"] += new_count
                    stats["duplicate_patents"] += duplicate_count
                    stats["patents_collected"] += len(patents)
                    stats["batches_processed"] += 1
                    batch_count += 1

                    logger.info(f"Batch {batch_count}: {len(patents)} patents, {new_count} new, {duplicate_count} duplicates")

                    # Check if more data available
                    if not next_cursor:
                        logger.info("No more data available")
                        break

                    cursor = next_cursor

                except Exception as e:
                    error_msg = f"Error in batch {batch_count + 1}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    break

        logger.info(f"Collection completed: {stats['new_patents']} new patents, {stats['duplicate_patents']} duplicates")
        return stats

    async def _fetch_batch(
        self,
        client: httpx.AsyncClient,
        query: Dict,
        cursor: Optional[List] = None
    ) -> Optional[Tuple[int, List[Dict], Optional[List]]]:
        """
        Fetch a single batch from PatentsView API using cursor pagination

        Args:
            client: httpx AsyncClient instance
            query: Query dict structure
            cursor: Cursor for pagination (array of [patent_year, patent_id])

        Returns:
            Tuple of (total_count, patents_list, next_cursor) or None on error
        """
        url = f"{self.base_url}/api/v1/patent/"

        # Build request payload - NO JSON encoding, send as objects!
        options = {
            "size": self.batch_size,
            "exclude_withdrawn": True
        }

        # Add cursor if provided
        if cursor:
            options["after"] = cursor

        payload = {
            "q": query,  # Send as dict, not JSON string
            "f": [
                "patent_id", "patent_title", "patent_abstract",
                "patent_date", "patent_year", "patent_type",
                "patent_num_us_patents_cited",
                "patent_num_times_cited_by_us_patents",
                "assignees"
            ],
            "s": [
                {"patent_year": "desc"},
                {"patent_id": "asc"}
            ],
            "o": options
        }

        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Extract cursor for next page from last record
            patents = data.get("patents", [])
            next_cursor = None

            if patents and len(patents) >= self.batch_size:
                # More data might be available
                last_patent = patents[-1]
                next_cursor = [
                    last_patent.get("patent_year"),
                    last_patent.get("patent_id")
                ]

            return (
                data.get("total_hits", 0),
                patents,
                next_cursor
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None

    def _save_patents(
        self,
        patents: List[Dict],
        technology_id: int
    ) -> Tuple[int, int]:
        """
        Save patents to database with duplicate detection

        Args:
            patents: List of patent dictionaries from API
            technology_id: ID of the technology

        Returns:
            Tuple of (new_count, duplicate_count)
        """
        new_count = 0
        duplicate_count = 0

        for patent_data in patents:
            try:
                patent = Patent(
                    technology_id=technology_id,
                    patent_id=patent_data.get("patent_id"),
                    patent_title=patent_data.get("patent_title", ""),
                    patent_abstract=patent_data.get("patent_abstract"),
                    patent_date=patent_data.get("patent_date"),
                    patent_year=patent_data.get("patent_year"),
                    patent_type=patent_data.get("patent_type"),
                    patent_num_us_patents_cited=patent_data.get("patent_num_us_patents_cited", 0),
                    patent_num_times_cited_by_us_patents=patent_data.get("patent_num_times_cited_by_us_patents", 0)
                )

                # Handle assignees (complex field using property)
                patent.assignees = patent_data.get("assignees", [])

                self.db.add(patent)
                self.db.commit()
                new_count += 1

            except IntegrityError:
                # Duplicate patent (violates unique constraint)
                self.db.rollback()
                duplicate_count += 1
                logger.debug(f"Duplicate patent skipped: {patent_data.get('patent_id')}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error saving patent {patent_data.get('patent_id')}: {str(e)}")

        return new_count, duplicate_count
