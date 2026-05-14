from typing import TypedDict


class GoogleAuthCredentials(TypedDict):
    """Dictionary containing OAuth client ID and secret."""

    client_id: str
    client_secret: str


class GoogleAuthDeviceCode(TypedDict):
    """Dictionary containing device code, user code, verification URL, and expiration time."""

    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
