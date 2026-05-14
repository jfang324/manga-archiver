import json
from pathlib import Path

import pytest

from src.manga_archiver.persistence.google_drive_token_store import (
    GoogleApiStoredToken,
    GoogleDriveTokenStore,
)


def _token() -> GoogleApiStoredToken:
    return GoogleApiStoredToken(
        token_uri="https://oauth2.googleapis.com/token",  # noqa: S106
        client_id="client-id",
        client_secret="client-secret",  # noqa: S106
        refresh_token="refresh-token",  # noqa: S106
    )


class TestGoogleDriveTokenStoreLoad:
    def test_load_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        store = GoogleDriveTokenStore(tmp_path / "token.json")

        token = store.load()

        assert token is None

    @pytest.mark.parametrize(
        "raw_token",
        [
            "{ invalid json",
            json.dumps([]),
            json.dumps("not an object"),
            json.dumps(123),
            json.dumps(
                {
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                }
            ),
            json.dumps(
                {
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "refresh_token": 123,
                }
            ),
        ],
        ids=[
            "malformed_json",
            "list_json",
            "string_json",
            "number_json",
            "missing_refresh_token",
            "non_string_refresh_token",
        ],
    )
    def test_load_returns_none_for_invalid_token_json(self, raw_token: str, tmp_path: Path) -> None:
        token_file = tmp_path / "token.json"
        token_file.write_text(raw_token)
        store = GoogleDriveTokenStore(token_file)

        token = store.load()

        assert token is None

    def test_load_returns_valid_token(self, tmp_path: Path) -> None:
        token_file = tmp_path / "token.json"
        expected_token = _token()
        token_file.write_text(json.dumps(expected_token))
        store = GoogleDriveTokenStore(token_file)

        token = store.load()

        assert token == expected_token


class TestGoogleDriveTokenStoreSave:
    def test_save_writes_token_json(self, tmp_path: Path) -> None:
        token_file = tmp_path / "nested" / "token.json"
        store = GoogleDriveTokenStore(token_file)
        token = _token()

        store.save(token)

        assert json.loads(token_file.read_text()) == token


class TestGoogleDriveTokenStoreDelete:
    def test_delete_removes_existing_token_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / "token.json"
        token_file.write_text(json.dumps(_token()))
        store = GoogleDriveTokenStore(token_file)

        store.delete()

        assert not token_file.exists()

    def test_delete_ignores_missing_token_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / "token.json"
        store = GoogleDriveTokenStore(token_file)

        store.delete()

        assert not token_file.exists()
