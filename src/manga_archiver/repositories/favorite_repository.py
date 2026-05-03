import asyncio

from ..db.database import get_connection
from ..models import ContentSource
from ..repositories.types import FavoriteManga


class FavoriteRepository:
    """Repository for managing favorite manga in the database."""

    async def get_all(self) -> list[FavoriteManga]:
        """Get all favorite manga from the database."""
        return await asyncio.to_thread(self._get_all)

    def _get_all(self) -> list[FavoriteManga]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, source FROM favorite_manga")
            rows = cursor.fetchall()

            return [
                FavoriteManga(id=row[0], title=row[1], source=ContentSource(row[2])) for row in rows
            ]

    async def create_one(self, favorite_manga: FavoriteManga) -> bool:
        """Add a manga to favorites."""
        return await asyncio.to_thread(self._create_one, favorite_manga)

    def _create_one(self, favorite_manga: FavoriteManga) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO favorite_manga (id, title, source) VALUES (?, ?, ?)",
                (favorite_manga.id, favorite_manga.title, str(favorite_manga.source)),
            )

            conn.commit()
            return cursor.rowcount > 0

    async def delete_by_id(self, manga_id: str) -> None:
        """Remove a manga from favorites by ID."""
        await asyncio.to_thread(self._delete_by_id, manga_id)

    def _delete_by_id(self, manga_id: str) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorite_manga WHERE id = ?", (manga_id,))

            conn.commit()
