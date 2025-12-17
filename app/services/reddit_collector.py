import httpx
import logging
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models import Technology, RedditPost

logger = logging.getLogger(__name__)


class RedditCollector:
    """Service for collecting posts from Reddit JSON API"""

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.reddit_base_url
        self.posts_limit = settings.reddit_posts_limit
        self.batch_size = settings.reddit_batch_size
        self.sort = settings.reddit_sort
        self.timeout = settings.request_timeout_seconds

    def build_query(self, technology: Technology) -> str:
        """
        Build Reddit search query from technology keywords and excluded terms

        Format: "keyword1" OR "keyword2" NOT "excluded term1" NOT "excluded term2"

        Args:
            technology: Technology object with keywords and excluded_terms

        Returns:
            Query string (httpx will handle URL-encoding)
        """
        # Build keywords part with OR operator
        keyword_parts = [f'"{kw}"' for kw in technology.keywords]
        query = ' OR '.join(keyword_parts)

        # Add excluded terms with NOT operator
        if technology.excluded_terms:
            excluded_parts = [f'NOT "{term}"' for term in technology.excluded_terms]
            query = f"{query} {' '.join(excluded_parts)}"

        return query

    async def collect_posts(self, technology_id: int) -> Dict:
        """
        Main collection method - orchestrates the entire collection process

        Args:
            technology_id: ID of the technology to collect posts for

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

        logger.info(f"Starting Reddit collection for technology '{technology.name}' (ID: {technology_id})")
        logger.info(f"Query: {query}")
        logger.info(f"Target: {self.posts_limit} posts")

        # Collection stats
        stats = {
            "technology_id": technology_id,
            "technology_name": technology.name,
            "posts_collected": 0,
            "total_posts_found": 0,
            "batches_processed": 0,
            "new_posts": 0,
            "duplicate_posts": 0,
            "errors": []
        }

        # Pagination - collect 250 posts in 3 batches (100+100+50)
        after = None
        batches = [100, 100, 50]  # Total 250 posts
        total_collected = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for batch_num, batch_limit in enumerate(batches, start=1):
                # Stop if we've reached the target
                if total_collected >= self.posts_limit:
                    break

                try:
                    # Fetch batch
                    result = await self._fetch_batch(
                        client=client,
                        query=query,
                        limit=batch_limit,
                        after=after
                    )

                    if result is None:
                        break  # API error, stop collection

                    total, posts, next_after = result

                    # First batch - record total
                    if batch_num == 1:
                        stats["total_posts_found"] = total
                        logger.info(f"Total posts found by Reddit: {total}")

                    # Save posts to database
                    new_count, duplicate_count = self._save_posts(
                        posts=posts,
                        technology_id=technology_id
                    )

                    stats["new_posts"] += new_count
                    stats["duplicate_posts"] += duplicate_count
                    stats["posts_collected"] += len(posts)
                    stats["batches_processed"] += 1
                    total_collected += len(posts)

                    logger.info(f"Batch {batch_num}: {len(posts)} posts, {new_count} new, {duplicate_count} duplicates")

                    # Check if more data available
                    if not next_after:
                        logger.info("No more data available from Reddit")
                        break

                    after = next_after

                except Exception as e:
                    error_msg = f"Error in batch {batch_num}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    break

        logger.info(f"Collection completed: {stats['new_posts']} new posts, {stats['duplicate_posts']} duplicates")
        return stats

    async def _fetch_batch(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        after: Optional[str] = None
    ) -> Optional[Tuple[int, List[Dict], Optional[str]]]:
        """
        Fetch a single batch from Reddit JSON API

        Args:
            client: httpx AsyncClient instance
            query: URL-encoded search query string
            limit: Number of posts to fetch (max 100)
            after: Pagination token (fullname of last post)

        Returns:
            Tuple of (total_count, posts_list, next_after) or None on error
        """
        url = f"{self.base_url}/search.json"

        params = {
            "q": query,
            "sort": self.sort,
            "type": "link",
            "limit": limit
        }

        if after:
            params["after"] = after

        headers = {
            "User-Agent": "HypeCycleCollector/1.0 (Technology trend analysis)"
        }

        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Reddit response structure: {"data": {"children": [...], "after": "..."}}
            children = data.get("data", {}).get("children", [])
            posts = [child.get("data", {}) for child in children]
            next_after = data.get("data", {}).get("after")
            dist = data.get("data", {}).get("dist", 0)  # Number of results in this batch

            return (dist, posts, next_after)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None

    def _save_posts(
        self,
        posts: List[Dict],
        technology_id: int
    ) -> Tuple[int, int]:
        """
        Save Reddit posts to database with duplicate detection

        Args:
            posts: List of post dictionaries from Reddit API
            technology_id: ID of the technology

        Returns:
            Tuple of (new_count, duplicate_count)
        """
        new_count = 0
        duplicate_count = 0

        for post_data in posts:
            try:
                reddit_post = RedditPost(
                    technology_id=technology_id,
                    post_id=post_data.get("id"),
                    title=post_data.get("title", ""),
                    selftext=post_data.get("selftext", ""),
                    score=post_data.get("score", 0),
                    num_comments=post_data.get("num_comments", 0),
                    author=post_data.get("author", "[deleted]"),
                    subreddit=post_data.get("subreddit", ""),
                    created_utc=post_data.get("created_utc", 0),
                    permalink=post_data.get("permalink", ""),
                    url=post_data.get("url", ""),
                    post_type="self" if post_data.get("is_self") else "link"
                )

                self.db.add(reddit_post)
                self.db.commit()
                new_count += 1

            except IntegrityError:
                # Duplicate post (violates unique constraint)
                self.db.rollback()
                duplicate_count += 1
                logger.debug(f"Duplicate post skipped: {post_data.get('id')}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Error saving post {post_data.get('id')}: {str(e)}")

        return new_count, duplicate_count
