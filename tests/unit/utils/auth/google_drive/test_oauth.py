from unittest.mock import MagicMock, patch

import requests

from src.manga_archiver.constants.exit_codes import (
    EXIT_AUTH_LOGIN_FAILED,
    EXIT_AUTH_LOGOUT_FAILED,
    EXIT_SUCCESS,
)
from src.manga_archiver.utils.auth.google_drive.oauth import (
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


def _configure_auth_pipeline(
    mock_get_path: MagicMock,
    mock_exists: MagicMock,
    mock_token_store: MagicMock,
    mock_load_creds: MagicMock,
) -> None:
    mock_get_path.return_value = "/valid/path"
    mock_exists.return_value = True
    mock_token_store.return_value.load.return_value = None
    mock_load_creds.return_value = MOCK_CREDENTIALS["installed"]


class TestHandleAuthLogin:
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.GoogleDriveTokenStore")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._poll_for_token")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._fetch_device_code")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._load_client_credentials")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.os.path.exists")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._get_credentials_path")
    def test_login_saves_token_and_returns_0_on_success(
        self,
        mock_get_path: MagicMock,
        mock_exists: MagicMock,
        mock_load_creds: MagicMock,
        mock_fetch: MagicMock,
        mock_poll: MagicMock,
        mock_token_store: MagicMock,
        capsys,
    ) -> None:
        _configure_auth_pipeline(
            mock_get_path,
            mock_exists,
            mock_token_store,
            mock_load_creds,
        )
        mock_fetch.return_value = MOCK_DEVICE_CODE
        mock_poll.return_value = "test_refresh_token"

        result = handle_auth_login()

        assert result == EXIT_SUCCESS
        assert "Authentication successful!" in capsys.readouterr().out
        mock_token_store.return_value.save.assert_called_once()
        saved_token = mock_token_store.return_value.save.call_args[0][0]
        assert saved_token["refresh_token"] == "test_refresh_token"  # noqa: S105
        assert saved_token["client_id"] == "test_client_id"

    @patch("src.manga_archiver.utils.auth.google_drive.oauth.GoogleDriveTokenStore")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._poll_for_token")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._fetch_device_code")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._load_client_credentials")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.os.path.exists")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._get_credentials_path")
    def test_login_returns_exit_auth_login_failed_on_network_error(
        self,
        mock_get_path: MagicMock,
        mock_exists: MagicMock,
        mock_load_creds: MagicMock,
        mock_fetch: MagicMock,
        _mock_poll: MagicMock,
        mock_token_store: MagicMock,
        capsys,
    ) -> None:
        _configure_auth_pipeline(
            mock_get_path,
            mock_exists,
            mock_token_store,
            mock_load_creds,
        )
        mock_fetch.side_effect = requests.Timeout("Connection timed out")

        result = handle_auth_login()

        assert result == EXIT_AUTH_LOGIN_FAILED
        assert "Network error" in capsys.readouterr().out

    @patch("src.manga_archiver.utils.auth.google_drive.oauth.GoogleDriveTokenStore")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._poll_for_token")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._fetch_device_code")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._load_client_credentials")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.os.path.exists")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth._get_credentials_path")
    def test_login_returns_exit_auth_login_failed_on_http_error(
        self,
        mock_get_path: MagicMock,
        mock_exists: MagicMock,
        mock_load_creds: MagicMock,
        mock_fetch: MagicMock,
        _mock_poll: MagicMock,
        mock_token_store: MagicMock,
        capsys,
    ) -> None:
        _configure_auth_pipeline(
            mock_get_path,
            mock_exists,
            mock_token_store,
            mock_load_creds,
        )
        mock_fetch.side_effect = requests.HTTPError("500 Server Error")

        result = handle_auth_login()

        assert result == EXIT_AUTH_LOGIN_FAILED
        assert "HTTP error" in capsys.readouterr().out


class TestHandleAuthLogout:
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.GoogleDriveTokenStore")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.requests.post")
    def test_logout_deletes_token_and_returns_0_on_success(
        self,
        mock_post: MagicMock,
        mock_token_store: MagicMock,
    ) -> None:
        mock_token_store.return_value.load.return_value = {"refresh_token": "test_refresh_token"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = handle_auth_logout()

        assert result == EXIT_SUCCESS
        mock_token_store.return_value.delete.assert_called_once()

    @patch("src.manga_archiver.utils.auth.google_drive.oauth.GoogleDriveTokenStore")
    @patch("src.manga_archiver.utils.auth.google_drive.oauth.requests.post")
    def test_logout_returns_exit_auth_logout_failed_on_network_error(
        self,
        mock_post: MagicMock,
        mock_token_store: MagicMock,
        capsys,
    ) -> None:
        mock_token_store.return_value.load.return_value = {"refresh_token": "test_refresh_token"}
        mock_post.side_effect = requests.Timeout("Connection timed out")

        result = handle_auth_logout()

        assert result == EXIT_AUTH_LOGOUT_FAILED
        assert "Network error" in capsys.readouterr().out
