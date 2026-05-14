import json
import os
import time

import requests

from ....constants.exit_codes import (
    EXIT_AUTH_LOGIN_FAILED,
    EXIT_AUTH_LOGOUT_FAILED,
    EXIT_SUCCESS,
)
from ....persistence import GoogleDriveTokenStore
from ....persistence.google_drive_token_store import GoogleApiStoredToken
from .constants import (
    CREDENTIALS_FILENAME,
    DEFAULT_AUTH_TIMEOUT_SECONDS,
    DEVICE_AUTH_URL,
    DRIVE_SCOPE,
    REVOKE_URL,
    TOKEN_URL,
)
from .enums import GoogleAuthDeviceFlowResult
from .types import GoogleAuthCredentials, GoogleAuthDeviceCode


def _get_credentials_path() -> str:
    """Get the absolute path to the OAuth client credentials file."""
    config_dir = os.path.expanduser("~/.manga-archiver")

    return os.path.join(config_dir, CREDENTIALS_FILENAME)


def _load_client_credentials(credentials_path: str) -> GoogleAuthCredentials:
    """Load OAuth client credentials from JSON file.

    Args:
        credentials_path: Absolute path to the credentials file

    Returns:
        GoogleAuthCredentials: a dictionary containing client credentials required for initiating OAuth flows
    """
    with open(credentials_path) as f:
        secrets = json.load(f)

    return secrets["installed"]


def _fetch_device_code(client_id: str) -> GoogleAuthDeviceCode:
    """Request a device code from Google for device flow authentication.

    Args:
        client_id: OAuth client ID

    Returns:
        GoogleAuthDeviceCode: a dictionary containing information to prompt user to complete device flow

    Raises:
        requests.HTTPError: If the request fails
        requests.Timeout: If the request exceeds 30 seconds
        requests.ConnectionError: If the connection fails
    """
    response = requests.post(
        DEVICE_AUTH_URL,
        data={"client_id": client_id, "scope": DRIVE_SCOPE},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def _poll_for_token(
    client_id: str, client_secret: str, device_code: str, timeout: int
) -> str | GoogleAuthDeviceFlowResult:
    """Poll for OAuth token after user authorizes device.

    Continuously polls the token endpoint until the user completes
    authorization or the timeout is reached.

    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        device_code: Device code from _fetch_device_code
        timeout: Maximum time to wait in seconds

    Returns:
        str | GoogleAuthDeviceFlowResult: Refresh token on success, or GoogleAuthDeviceFlowResult on failure

    Raises:
        requests.Timeout: If a request exceeds 30 seconds
        requests.ConnectionError: If the connection fails
    """
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
            timeout=30,
        )

        if token_response.status_code == 200:
            token_data = token_response.json()
            return token_data.get("refresh_token")

        if token_response.status_code == 400:
            error_data = token_response.json()
            error = error_data.get("error", "")

            if error == GoogleAuthDeviceFlowResult.AUTHORIZATION_PENDING:
                continue

            if error == GoogleAuthDeviceFlowResult.SLOW_DOWN:
                interval += 5

            if error == GoogleAuthDeviceFlowResult.ACCESS_DENIED:
                return GoogleAuthDeviceFlowResult.ACCESS_DENIED

            if error == GoogleAuthDeviceFlowResult.EXPIRED_TOKEN:
                return GoogleAuthDeviceFlowResult.EXPIRED_TOKEN

    return GoogleAuthDeviceFlowResult.TIMEOUT


async def handle_auth_login() -> int:
    """Handle the auth google-drive login command using device flow.

    Initiates OAuth device flow authentication with Google Drive.
    Prompts user to visit a URL and enter a code, then polls for completion.

    Returns:
        int: EXIT_SUCCESS on success, EXIT_AUTH_LOGIN_FAILED on failure
    """
    credentials_path = _get_credentials_path()
    token_store = GoogleDriveTokenStore()

    if not os.path.exists(credentials_path):
        print(
            f"Credentials file not found: {credentials_path}\n"
            "Please download your OAuth client credentials from Google Cloud Console "
            "and save them to this location."
        )
        return EXIT_AUTH_LOGIN_FAILED

    if await token_store.load() is not None:
        print("Already authenticated. Run 'auth google-drive logout' first to re-authenticate.")
        return EXIT_SUCCESS

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

        if result == GoogleAuthDeviceFlowResult.ACCESS_DENIED:
            print("Access denied. Please try again.")
            return EXIT_AUTH_LOGIN_FAILED

        if result == GoogleAuthDeviceFlowResult.EXPIRED_TOKEN:
            print("Authentication timed out. Please try again.")
            return EXIT_AUTH_LOGIN_FAILED

        if result == GoogleAuthDeviceFlowResult.TIMEOUT:
            print("Authentication timed out. Please try again.")
            return EXIT_AUTH_LOGIN_FAILED

        if result:
            await token_store.save(
                GoogleApiStoredToken(
                    token_uri=TOKEN_URL,
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=str(result),
                )
            )
            print("Authentication successful!")
            return EXIT_SUCCESS

        print("Authentication failed. Please try again.")
        return EXIT_AUTH_LOGIN_FAILED

    except (requests.Timeout, requests.ConnectionError) as e:
        print(f"Network error during authentication: {e}")
        return EXIT_AUTH_LOGIN_FAILED
    except requests.HTTPError as e:
        print(f"HTTP error during authentication: {e}")
        return EXIT_AUTH_LOGIN_FAILED
    except Exception as e:
        print(f"Failed to complete authentication: {e}")
        return EXIT_AUTH_LOGIN_FAILED


async def handle_auth_logout() -> int:
    """Handle the auth google-drive logout command.

    Revokes the OAuth refresh token and deletes local credentials.

    Returns:
        int: EXIT_SUCCESS on success, EXIT_AUTH_LOGOUT_FAILED on failure
    """
    token_store = GoogleDriveTokenStore()
    token = await token_store.load()

    if not token:
        print("Not authenticated. Run 'auth google-drive login' first.")
        return EXIT_SUCCESS

    if not token.get("refresh_token"):
        print("Not authenticated. Run 'auth google-drive login' first.")
        return EXIT_SUCCESS

    try:
        response = requests.post(
            REVOKE_URL,
            params={"token": token["refresh_token"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code == 200:
            try:
                await token_store.delete()
            except OSError as e:
                print(f"Failed to remove local credentials: {e}")
                return EXIT_AUTH_LOGOUT_FAILED

            print("Successfully logged out.")
            return EXIT_SUCCESS
        print(f"Failed to revoke token: {response.text}")
        return EXIT_AUTH_LOGOUT_FAILED
    except requests.HTTPError as e:
        print(f"Failed to send revocation request: {e}")
        return EXIT_AUTH_LOGOUT_FAILED
    except (requests.Timeout, requests.ConnectionError) as e:
        print(f"Network error: {e}")
        return EXIT_AUTH_LOGOUT_FAILED
