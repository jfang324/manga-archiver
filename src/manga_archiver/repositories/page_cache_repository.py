import json

from ..db.database import get_connection
from ..models import ContentSource

SUPPORTED_SOURCES: set[ContentSource] = {ContentSource.ALLMANGA}
MAX_CACHE_SIZE = 10000  # max number of cached chapters
EVICT_COUNT = 1000  # number of oldest entries to remove when limit reached


class PageCacheRepository:
    """Repository for caching page URLs to reduce API calls."""

    def get(self, source: ContentSource, chapter_id: str) -> list[str] | None:
        """Retrieve cached URLs for a chapter.

        Args:
            source: Content source
            chapter_id: Chapter ID

        Returns:
            list[str]: List of URLs if cached, None otherwise
        """
        if source not in SUPPORTED_SOURCES:
            return None

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT urls FROM page_cache WHERE source = ? AND chapter_id = ?",
                (source.value, chapter_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            try:
                urls = json.loads(row[0])
            except json.JSONDecodeError:
                self.delete(source, chapter_id)
                return None

            if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
                self.delete(source, chapter_id)
                return None

            return urls

    def set(self, source: ContentSource, chapter_id: str, urls: list[str]) -> None:
        """Store URLs for a chapter in the cache.

        Args:
            source: Content source
            chapter_id: Chapter ID
            urls: List of URLs to cache
        """
        if source not in SUPPORTED_SOURCES:
            return

        self._ensure_capacity()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO page_cache (source, chapter_id, urls)
                VALUES (?, ?, ?)
                ON CONFLICT(source, chapter_id) DO UPDATE SET urls = excluded.urls
                """,
                (source.value, chapter_id, json.dumps(urls)),
            )
            conn.commit()

    def delete(self, source: ContentSource, chapter_id: str) -> None:
        """Delete a cached entry.

        Args:
            source: Content source
            chapter_id: Chapter ID
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM page_cache WHERE source = ? AND chapter_id = ?",
                (source.value, chapter_id),
            )
            conn.commit()

    def _ensure_capacity(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM page_cache")
            count = cursor.fetchone()[0]

            if count >= MAX_CACHE_SIZE:
                cursor.execute(
                    """
                    DELETE FROM page_cache
                    WHERE (source, chapter_id) IN (
                        SELECT source, chapter_id
                        FROM page_cache
                        ORDER BY created_at ASC
                        LIMIT ?
                    )
                    """,
                    (EVICT_COUNT,),
                )
                conn.commit()
