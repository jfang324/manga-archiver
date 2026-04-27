from sqlite3 import connect
from unittest.mock import patch

from src.manga_archiver.db.database import init_db
from src.manga_archiver.models import ContentSource
from src.manga_archiver.repositories.favorite_repository import FavoriteRepository
from src.manga_archiver.repositories.types import FavoriteManga


class TestFavoriteRepository:
    @patch("src.manga_archiver.repositories.favorite_repository.get_connection")
    def test_create_one_returns_whether_favorite_was_created(self, mock_get_connection) -> None:
        conn = connect(":memory:")
        init_db(conn)
        mock_get_connection.return_value = conn

        favorite = FavoriteManga(id="manga_1", title="Test Manga", source=ContentSource.MANGADEX)

        repository = FavoriteRepository()

        assert repository.create_one(favorite) is True
        assert repository.create_one(favorite) is False

        cursor = conn.cursor()
        cursor.execute("SELECT id, title, source FROM favorite_manga")

        assert cursor.fetchall() == [("manga_1", "Test Manga", "mangadex")]
