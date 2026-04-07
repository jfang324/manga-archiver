from unittest.mock import MagicMock, patch

import pytest
import requests

from src.mangadex_downloader.utils.auth.google_drive.enums import (
    GoogleAuthDeviceFlowResult,
)
from src.mangadex_downloader.utils.auth.google_drive.oauth import (
    handle_auth_login,
    handle_auth_logout,
)

MOCK_CREDENTIALS = {
    "installed": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
}

MOCK_DEVICE_CODE = {
    "device_code": "test_device_code",
    "user_code": "ABCD-EFGH",
    "verification_url": "https://google.com/device",
    "expires_in": 300,
}


@pytest.fixture
def mock_auth_env():
    """Set up the base environment for auth tests (credentials path, file exists, no existing token)."""
    with (
        patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth._get_credentials_path"
        ) as mock_get_path,
        patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth.os.path.exists"
        ) as mock_exists,
        patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth.load_token"
        ) as mock_load_token,
    ):
        mock_get_path.return_value = "/valid/path"
        mock_exists.return_value = True
        mock_load_token.return_value = None

        yield mock_get_path, mock_exists, mock_load_token


@pytest.fixture
def mock_auth_pipeline(mock_auth_env):
    """Set up the full auth pipeline (credentials + device code fetch + token polling)."""
    mock_get_path, mock_exists, mock_load_token = mock_auth_env

    with (
        patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth._load_client_credentials"
        ) as mock_load_creds,
        patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth._fetch_device_code"
        ) as mock_fetch,
        patch("src.mangadex_downloader.utils.auth.google_drive.oauth._poll_for_token") as mock_poll,
    ):
        mock_load_creds.return_value = MOCK_CREDENTIALS["installed"]

        yield mock_load_creds, mock_fetch, mock_poll, mock_get_path, mock_exists, mock_load_token


class TestHandleAuthLogin:
    def test_login_returns_1_when_credentials_file_missing(self, capsys):
        with patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth._get_credentials_path"
        ) as mock_get_path:
            mock_get_path.return_value = "/nonexistent/path"

            result = handle_auth_login()

        assert result == 1
        assert "Credentials file not found" in capsys.readouterr().out

    def test_login_returns_0_when_already_authenticated(self, mock_auth_env, capsys):
        _, _, mock_load_token = mock_auth_env
        mock_load_token.return_value = {"refresh_token": "existing_token"}

        result = handle_auth_login()

        assert result == 0
        assert "Already authenticated" in capsys.readouterr().out

    def test_login_saves_token_and_returns_0_on_success(self, mock_auth_pipeline, capsys):
        mock_load_creds, mock_fetch, mock_poll, *_ = mock_auth_pipeline
        mock_fetch.return_value = MOCK_DEVICE_CODE
        mock_poll.return_value = "test_refresh_token"

        with patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth.save_token"
        ) as mock_save_token:
            result = handle_auth_login()

        assert result == 0
        assert "Authentication successful!" in capsys.readouterr().out
        mock_save_token.assert_called_once()
        saved_token = mock_save_token.call_args[0][0]
        assert saved_token["refresh_token"] == "test_refresh_token"  # noqa: S105
        assert saved_token["client_id"] == "test_client_id"

    def test_login_returns_1_on_network_error(self, mock_auth_pipeline, capsys):
        _, mock_fetch, _, *_ = mock_auth_pipeline
        mock_fetch.side_effect = requests.Timeout("Connection timed out")

        result = handle_auth_login()

        assert result == 1
        assert "Network error" in capsys.readouterr().out

    def test_login_returns_1_on_http_error(self, mock_auth_pipeline, capsys):
        _, mock_fetch, _, *_ = mock_auth_pipeline
        mock_fetch.side_effect = requests.HTTPError("500 Server Error")

        result = handle_auth_login()

        assert result == 1
        assert "Server error" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "poll_result, expected_message",
        [
            (GoogleAuthDeviceFlowResult.ACCESS_DENIED, "Access denied"),
            (GoogleAuthDeviceFlowResult.EXPIRED_TOKEN, "timed out"),
            (GoogleAuthDeviceFlowResult.TIMEOUT, "timed out"),
        ],
        ids=["access_denied", "expired_token", "timeout"],
    )
    def test_login_returns_1_on_auth_failure(
        self, mock_auth_pipeline, poll_result, expected_message, capsys
    ):
        _, mock_fetch, mock_poll, *_ = mock_auth_pipeline
        mock_fetch.return_value = MOCK_DEVICE_CODE
        mock_poll.return_value = poll_result

        result = handle_auth_login()

        assert result == 1
        assert expected_message in capsys.readouterr().out


class TestHandleAuthLogout:
    def test_logout_returns_0_when_not_authenticated(self, capsys):
        with patch(
            "src.mangadex_downloader.utils.auth.google_drive.oauth.load_token"
        ) as mock_load_token:
            mock_load_token.return_value = None

            result = handle_auth_logout()

        assert result == 0
        assert "Not authenticated" in capsys.readouterr().out

    def test_logout_deletes_token_and_returns_0_on_success(self):
        with (
            patch(
                "src.mangadex_downloader.utils.auth.google_drive.oauth.load_token"
            ) as mock_load_token,
            patch(
                "src.mangadex_downloader.utils.auth.google_drive.oauth.requests.post"
            ) as mock_post,
            patch(
                "src.mangadex_downloader.utils.auth.google_drive.oauth.delete_token"
            ) as mock_delete_token,
        ):
            mock_load_token.return_value = {"refresh_token": "test_refresh_token"}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = handle_auth_logout()

        assert result == 0
        mock_delete_token.assert_called_once()

    def test_logout_returns_1_on_network_error(self, capsys):
        with (
            patch(
                "src.mangadex_downloader.utils.auth.google_drive.oauth.load_token"
            ) as mock_load_token,
            patch(
                "src.mangadex_downloader.utils.auth.google_drive.oauth.requests.post"
            ) as mock_post,
        ):
            mock_load_token.return_value = {"refresh_token": "test_refresh_token"}
            mock_post.side_effect = requests.Timeout("Connection timed out")

            result = handle_auth_logout()

        assert result == 1
        assert "Network error" in capsys.readouterr().out
