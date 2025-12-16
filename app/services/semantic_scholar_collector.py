import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models import Technology, Paper

logger = logging.getLogger(__name__)


class SemanticScholarCollector:
    """Service for collecting papers from Semantic Scholar bulk API"""

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.semantic_scholar_base_url
        self.api_key = settings.semantic_scholar_api_key
        self.max_batches = settings.max_batches_per_collection
        self.timeout = settings.request_timeout_seconds

    def build_query(self, technology: Technology) -> str:
        """
        Build Semantic Scholar query from technology keywords and excluded terms

        Format: ("keyword1" | "keyword2" | "keyword3") -"excluded term1" -"excluded term2"

        Args:
            technology: Technology object with keywords and excluded_terms

        Returns:
            Formatted query string
        """
        # Quote each keyword and join with OR operator
        keyword_parts = [f'"{kw}"' for kw in technology.keywords]
        query = f"({' | '.join(keyword_parts)})"

        # Add excluded terms with minus operator (each term wrapped in quotes)
        if technology.excluded_terms:
            excluded_parts = [f'-"{term}"' for term in technology.excluded_terms]
            query = f"{query} {' '.join(excluded_parts)}"

        return query

    def get_date_range(self) -> Tuple[str, str]:
        """
        Calculate date range for paper collection

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * settings.paper_lookback_years)
        return (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    async def collect_papers(self, technology_id: int) -> Dict:
        """
        Main collection method - orchestrates the entire collection process

        Args:
            technology_id: ID of the technology to collect papers for

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
        start_date, end_date = self.get_date_range()

        logger.info(f"Starting collection for technology '{technology.name}' (ID: {technology_id})")
        logger.info(f"Query: {query}")
        logger.info(f"Date range: {start_date} to {end_date}")

        # Collection stats
        stats = {
            "technology_id": technology_id,
            "technology_name": technology.name,
            "papers_collected": 0,
            "total_papers_found": 0,
            "batches_processed": 0,
            "new_papers": 0,
            "duplicate_papers": 0,
            "errors": []
        }

        # Pagination
        continuation_token = None
        batch_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:  # Collect all papers without batch limit
                try:
                    # Fetch batch
                    result = await self._fetch_batch(
                        client=client,
                        query=query,
                        start_date=start_date,
                        end_date=end_date,
                        token=continuation_token
                    )

                    if result is None:
                        break  # API error, stop collection

                    total, papers, next_token = result

                    # First batch - record total
                    if batch_count == 0:
                        stats["total_papers_found"] = total
                        logger.info(f"Total papers found: {total}")

                    # Save papers to database
                    new_count, duplicate_count = self._save_papers(
                        papers=papers,
                        technology_id=technology_id
                    )

                    stats["new_papers"] += new_count
                    stats["duplicate_papers"] += duplicate_count
                    stats["papers_collected"] += len(papers)
                    stats["batches_processed"] += 1
                    batch_count += 1

                    logger.info(f"Batch {batch_count}: {len(papers)} papers, {new_count} new, {duplicate_count} duplicates")

                    # Check if more data available
                    if not next_token:
                        logger.info("No more data available")
                        break

                    continuation_token = next_token

                except Exception as e:
                    error_msg = f"Error in batch {batch_count + 1}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    break

        logger.info(f"Collection completed: {stats['new_papers']} new papers, {stats['duplicate_papers']} duplicates")
        return stats

    async def _fetch_batch(
        self,
        client: httpx.AsyncClient,
        query: str,
        start_date: str,
        end_date: str,
        token: Optional[str] = None
    ) -> Optional[Tuple[int, List[Dict], Optional[str]]]:
        """
        Fetch a single batch from Semantic Scholar API

        Args:
            client: httpx AsyncClient instance
            query: Search query string
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            token: Continuation token for pagination

        Returns:
            Tuple of (total_count, papers_list, next_token) or None on error
        """
        url = f"{self.base_url}/paper/search/bulk"

        params = {
            "query": query,
            "fields": "paperId,title,year,citationCount,publicationDate,abstract,authors,venue,s2FieldsOfStudy,openAccessPdf",
            "publicationDateOrYear": f"{start_date}:{end_date}"
        }

        if token:
            params["token"] = token

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            return (
                data.get("total", 0),
                data.get("data", []),
                data.get("token")
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

    def _save_papers(
        self,
        papers: List[Dict],
        technology_id: int
    ) -> Tuple[int, int]:
        """
        Save papers to database with duplicate detection

        Args:
            papers: List of paper dictionaries from API
            technology_id: ID of the technology

        Returns:
            Tuple of (new_count, duplicate_count)
        """
        new_count = 0
        duplicate_count = 0

        for paper_data in papers:
            try:
                paper = Paper(
                    technology_id=technology_id,
                    paper_id=paper_data.get("paperId"),
                    title=paper_data.get("title", ""),
                    year=paper_data.get("year"),
                    citation_count=paper_data.get("citationCount", 0),
                    publication_date=paper_data.get("publicationDate"),
                    abstract=paper_data.get("abstract"),
                    venue=paper_data.get("venue")
                )

                # Handle complex fields using properties
                paper.authors = paper_data.get("authors", [])
                paper.s2_fields_of_study = paper_data.get("s2FieldsOfStudy", [])

                # Handle openAccessPdf (can be dict or None)
                open_access = paper_data.get("openAccessPdf")
                if open_access and isinstance(open_access, dict):
                    paper.open_access_pdf = open_access.get("url")
                else:
                    paper.open_access_pdf = None

                self.db.add(paper)
                self.db.commit()
                new_count += 1

            except IntegrityError:
                # Duplicate paper (violates unique constraint)
                self.db.rollback()
                duplicate_count += 1
                logger.debug(f"Duplicate paper skipped: {paper_data.get('paperId')}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error saving paper {paper_data.get('paperId')}: {str(e)}")

        return new_count, duplicate_count
