import logging

from ..db.database import get_connection
from ..repositories.types import FavoriteManga
from ..types import ContentSource

logger = logging.getLogger(__name__)


class FavoriteRepository:
    """Repository for managing favorite manga in the database."""

    def get_all(self) -> list[FavoriteManga]:
        """Get all favorite manga from the database."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, source FROM favorite_manga")
                rows = cursor.fetchall()

                return [
                    FavoriteManga(id=row[0], title=row[1], source=ContentSource(row[2]))
                    for row in rows
                ]
        except Exception as e:
            logger.error("Failed to get favorites: %s", e)
            return []

    def create_one(self, favorite_manga: FavoriteManga) -> None:
        """Add a manga to favorites."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO favorite_manga (id, title, source) VALUES (?, ?, ?)",
                    (favorite_manga["id"], favorite_manga["title"], str(favorite_manga["source"])),
                )

                conn.commit()
        except Exception as e:
            logger.error("Failed to create favorite: %s", e)
            raise

    def delete_by_id(self, manga_id: str) -> None:
        """Remove a manga from favorites by ID."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM favorite_manga WHERE id = ?", (manga_id,))

                conn.commit()
        except Exception as e:
            logger.error("Failed to delete favorite: %s", e)
            raise
