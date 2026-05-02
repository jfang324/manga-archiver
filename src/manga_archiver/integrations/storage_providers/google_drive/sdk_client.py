import asyncio
import io
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from ...exceptions import ApiError, RateLimitError
from .constants import DEFAULT_CHUNK_SIZE, DEFAULT_MAX_RETRIES, MULTIPART_UPLOAD_THRESHOLD
from .types import (
    GoogleApiStoredToken,
    GoogleDriveDirectory,
    GoogleDriveFile,
    GoogleDriveFolderMetadata,
)


def _escape_query_string(value: str) -> str:
    """Escape special characters for Google Drive API query strings."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveSdkClient:
    """Async wrapper around the synchronous Google Drive SDK."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._credentials = Credentials(
            token=None,
            refresh_token=stored_token["refresh_token"],
            client_id=stored_token["client_id"],
            client_secret=stored_token["client_secret"],
            token_uri=stored_token["token_uri"],
        )
        self._service = build("drive", "v3", credentials=self._credentials)
        self._max_retries = max_retries

    def _list_items_sync(
        self,
        query: str,
        page_size: int | None = None,
        spaces: str | None = None,
    ) -> list[GoogleDriveDirectory] | list[GoogleDriveFile]:
        items: list[GoogleDriveDirectory] | list[GoogleDriveFile] = []
        page_token: str | None = None

        while True:
            results = (
                self._service.files()
                .list(
                    q=query,
                    spaces=spaces,
                    fields="files(id, name, appProperties), nextPageToken",
                    pageSize=page_size,
                    pageToken=page_token,
                )
                .execute()
            )
            items.extend(results.get("files", []))

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return items

    def list_root_folders(
        self, root_folder_name: str, page_size: int | None = None
    ) -> list[GoogleDriveDirectory]:
        """List matching root folders in My Drive."""
        # TODO: Convert list_root_folders/list_sub_folders/list_files_in_folder to async after sync callers move up.  # noqa: FIX002
        query = (
            f"name='{_escape_query_string(root_folder_name)}' and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )

        return self._list_items_sync(query, page_size, spaces="drive")

    def list_sub_folders(
        self, parent_id: str, page_size: int | None = None
    ) -> list[GoogleDriveDirectory]:
        """List subfolders under a parent folder."""
        query = (
            f"'{_escape_query_string(parent_id)}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )

        return self._list_items_sync(query, page_size)

    def list_files_in_folder(
        self, folder_id: str, page_size: int | None = None
    ) -> list[GoogleDriveFile]:
        """List files under a parent folder."""
        query = f"'{_escape_query_string(folder_id)}' in parents and trashed=false"

        return self._list_items_sync(query, page_size)

    def _create_folder_sync(
        self,
        name: str,
        folder_metadata: GoogleDriveFolderMetadata,
        parent_id: str | None = None,
    ) -> str:
        """Create a new folder in Google Drive."""
        file_metadata: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "appProperties": folder_metadata.to_app_properties(),
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        folder = self._service.files().create(body=file_metadata).execute()

        return folder["id"]

    async def create_folder(
        self,
        name: str,
        folder_metadata: GoogleDriveFolderMetadata,
        parent_id: str | None = None,
    ) -> str:
        """Create a new folder without blocking the event loop."""
        return await asyncio.to_thread(
            self._create_folder_sync,
            name,
            folder_metadata,
            parent_id,
        )

    def _search_folder_by_name_sync(self, name: str, parent_id: str, source: str) -> str | None:
        """Search for a folder by name, parent, and source metadata."""
        query = (
            f"name='{_escape_query_string(name)}' and "
            f"'{_escape_query_string(parent_id)}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false and "
            f"appProperties has {{ key='source' and value='{_escape_query_string(source)}' }}"
        )

        files = self._list_items_sync(query, page_size=1)
        return files[0]["id"] if files else None

    async def search_folder_by_name(self, name: str, parent_id: str, source: str) -> str | None:
        """Search for a folder without blocking the event loop."""
        return await asyncio.to_thread(
            self._search_folder_by_name_sync,
            name,
            parent_id,
            source,
        )

    def update_metadata(self, item_id: str, app_properties: dict[str, str]) -> None:
        """Update file or folder appProperties."""
        # TODO: Convert public SDK metadata updates to async after migrations move up.  # noqa: FIX002
        self._service.files().update(
            fileId=item_id,
            body={"appProperties": app_properties},
        ).execute()

    def _upload_file_sync(
        self,
        file_data: bytes,
        file_name: str,
        folder_id: str,
        mimetype: str,
        app_properties: dict[str, str],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        attempts: int = 1,
    ) -> str | None:
        """Upload a file to Google Drive."""
        name = Path(file_name).stem
        extension = Path(file_name).suffix

        upload_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "appProperties": app_properties,
        }

        should_use_resumable_upload = len(file_data) > MULTIPART_UPLOAD_THRESHOLD

        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=should_use_resumable_upload,
            chunksize=chunk_size,
        )

        try:
            file = (
                self._service.files()
                .create(body=upload_metadata, media_body=media, fields="id")
                .execute()
            )

            return file.get("id")
        except HttpError as e:
            if e.resp.status == 409:
                if attempts < self._max_retries:
                    return self._upload_file_sync(
                        file_data,
                        f"{name} ({attempts}){extension}",
                        folder_id,
                        mimetype,
                        app_properties,
                        chunk_size,
                        attempts + 1,
                    )
                raise ApiError(f"Upload failed: max retries exceeded for {file_name}") from e

            if e.resp.status == 403:
                raise ApiError(f"Permission denied (403): {file_name}") from e

            if e.resp.status == 429:
                raise RateLimitError(f"Rate limit exceeded: {file_name}") from e

            raise

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        folder_id: str,
        mimetype: str,
        app_properties: dict[str, str],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> str | None:
        """Upload a file without blocking the event loop."""
        return await asyncio.to_thread(
            self._upload_file_sync,
            file_data,
            file_name,
            folder_id,
            mimetype,
            app_properties,
            chunk_size,
        )
