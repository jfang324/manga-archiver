from typing import TypedDict


class GoogleApiStoredToken(TypedDict):
    """Dictionary containing metadata for google.oauth2.credentials.Credentials."""

    token_uri: str
    client_id: str
    client_secret: str
    refresh_token: str


class GoogleDriveDirectory(TypedDict):
    """Dictionary containing metadata for a Google Drive directory."""

    id: str
    name: str
