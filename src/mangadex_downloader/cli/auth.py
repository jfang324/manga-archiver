import json
import logging
import os
import time

import requests

from ..utils import delete_token, load_token, save_token

logger = logging.getLogger(__name__)

DEFAULT_AUTH_TIMEOUT_SECONDS = 300

CREDENTIALS_FILENAME = "client_secret.json"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DEVICE_AUTH_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def _get_credentials_path() -> str:
    config_dir = os.path.expanduser("~/.mangadex-downloader")
    return os.path.join(config_dir, CREDENTIALS_FILENAME)


def _load_client_credentials(credentials_path: str) -> dict:
    with open(credentials_path) as f:
        secrets = json.load(f)
    return secrets["installed"]


def _fetch_device_code(client_id: str) -> dict:
    response = requests.post(
        DEVICE_AUTH_URL,
        data={"client_id": client_id, "scope": DRIVE_SCOPE},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()


def _poll_for_token(
    client_id: str, client_secret: str, device_code: str, timeout: int
) -> str | None:
    interval = 5
    start_time = time.time()

    while time.time() - start_time < timeout:
        time.sleep(interval)

        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code == 200:
            token_data = token_response.json()
            return token_data.get("refresh_token")

        if token_response.status_code == 400:
            error_data = token_response.json()
            error = error_data.get("error", "")

            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
            if error == "access_denied":
                return "access_denied"
            if error == "expired_token":
                return "expired_token"

        logger.error("Unexpected token response: %s", token_response.text)

    return "timeout"


def handle_auth_login() -> int:
    """Handle the auth login command using device flow."""
    credentials_path = _get_credentials_path()

    if not os.path.exists(credentials_path):
        print(
            f"Credentials file not found: {credentials_path}\n"
            "Please download your OAuth client credentials from Google Cloud Console "
            "and save them to this location."
        )
        return 1

    if load_token() is not None:
        print("Already authenticated. Run 'auth logout' first to re-authenticate.")
        return 0

    try:
        client_credentials = _load_client_credentials(credentials_path)
        client_id = client_credentials["client_id"]
        client_secret = client_credentials["client_secret"]

        code_info = _fetch_device_code(client_id)
        user_code = code_info["user_code"]
        verification_url = code_info["verification_url"]
        expires_in = code_info["expires_in"]

        print("==========================================")
        print("       GOOGLE DRIVE AUTHENTICATION        ")
        print("==========================================")
        print()
        print(f"1. Go to: {verification_url}")
        print(f"2. Enter this code: {user_code}")
        print()
        print(f"Code expires in {expires_in // 60} minutes.")
        print("==========================================")
        print()

        result = _poll_for_token(
            client_id,
            client_secret,
            code_info["device_code"],
            DEFAULT_AUTH_TIMEOUT_SECONDS,
        )

        if result == "access_denied":
            print("Access denied. Please try again.")
            return 1
        if result == "expired_token":
            print("Authentication timed out. Please try again.")
            return 1
        if result == "timeout":
            print("Authentication timed out. Please try again.")
            return 1
        if result:
            save_token(
                {
                    "refresh_token": result,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "token_uri": TOKEN_URL,
                }
            )
            print("Authentication successful!")
            return 0

        print("Authentication failed. Please try again.")
        return 1

    except Exception as e:
        logger.error("Failed to complete authentication: %s", e)
        print(f"Error: {e}")
        return 1


def handle_auth_logout() -> int:
    """Handle the auth logout command."""
    token = load_token()
    if token:
        refresh_token = token.get("refresh_token")
        if refresh_token:
            try:
                requests.post(
                    REVOKE_URL,
                    params={"token": refresh_token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except Exception as e:
                logger.warning("Failed to revoke token: %s", e)

    delete_token()
    print("Logged out of Google Drive")
    return 0
