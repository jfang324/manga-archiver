from sqlite3 import connect
from unittest.mock import patch

from src.manga_archiver.db.database import init_db
from src.manga_archiver.models import ContentSource
from src.manga_archiver.repositories.favorite_repository import FavoriteRepository
from src.manga_archiver.repositories.types import FavoriteManga


class TestFavoriteRepository:
    @patch("src.manga_archiver.repositories.favorite_repository.get_connection")
    async def test_create_one_returns_whether_favorite_was_created(
        self, mock_get_connection
    ) -> None:
        conn = connect(":memory:", check_same_thread=False)
        init_db(conn)
        mock_get_connection.return_value = conn

        favorite = FavoriteManga(id="manga_1", title="Test Manga", source=ContentSource.MANGADEX)

        repository = FavoriteRepository()

        assert await repository.create_one(favorite) is True
        assert await repository.create_one(favorite) is False

        cursor = conn.cursor()
        cursor.execute("SELECT id, title, source FROM favorite_manga")

        assert cursor.fetchall() == [("manga_1", "Test Manga", "mangadex")]

    @patch("src.manga_archiver.repositories.favorite_repository.get_connection")
    async def test_get_all_returns_stored_favorites(self, mock_get_connection) -> None:
        conn = connect(":memory:", check_same_thread=False)
        init_db(conn)
        mock_get_connection.return_value = conn
        conn.execute(
            "INSERT INTO favorite_manga (id, title, source) VALUES (?, ?, ?)",
            ("manga_1", "Test Manga", "allmanga"),
        )
        conn.commit()

        repository = FavoriteRepository()

        assert await repository.get_all() == [
            FavoriteManga(id="manga_1", title="Test Manga", source=ContentSource.ALLMANGA)
        ]

    @patch("src.manga_archiver.repositories.favorite_repository.get_connection")
    async def test_delete_by_id_removes_favorite(self, mock_get_connection) -> None:
        conn = connect(":memory:", check_same_thread=False)
        init_db(conn)
        mock_get_connection.return_value = conn
        conn.execute(
            "INSERT INTO favorite_manga (id, title, source) VALUES (?, ?, ?)",
            ("manga_1", "Test Manga", "mangadex"),
        )
        conn.commit()

        repository = FavoriteRepository()

        await repository.delete_by_id("manga_1")

        cursor = conn.cursor()
        cursor.execute("SELECT id, title, source FROM favorite_manga")

        assert cursor.fetchall() == []
