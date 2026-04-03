import asyncio
import io
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from ...exceptions import RateLimitError
from .constants import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_ROOT_PAGE_SIZE,
    DEFAULT_SUB_FOLDER_PAGE_SIZE,
    ROOT_FOLDER_NAME,
)
from .types import GoogleApiStoredToken, GoogleDriveDirectory

logger = logging.getLogger(__name__)


class GoogleDriveClient:
    """Client for interacting with Google Drive API for cloud storage. Must call initialize() after construction before using other methods."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize the Google Drive client.

        Args:
            stored_token: The token stored by the corresponding auth util
            max_retries: Maximum number of retries for failed uploads (default: 5)
        """
        self._credentials = Credentials(
            token=None,
            refresh_token=stored_token["refresh_token"],
            client_id=stored_token["client_id"],
            client_secret=stored_token["client_secret"],
            token_uri=stored_token["token_uri"],
        )
        self._service = build("drive", "v3", credentials=self._credentials)
        self._root_folder_id: str | None = None
        self._folder_cache: dict[str, str] = {}
        self._max_retries = max_retries

    def initialize(self) -> str:
        """Initialize and cache folders from Google Drive.

        Searches for the root MangaDex-Downloader folder, creates it if not
        found, then caches all existing manga subfolders.

        Returns:
            str: The ID of the root folder
        """
        print("Initializing Google Drive...")

        root_folders = self._get_root_folders(page_size=DEFAULT_ROOT_PAGE_SIZE)

        for folder in root_folders:
            if folder["name"] == ROOT_FOLDER_NAME:
                self._root_folder_id = folder["id"]
                break

        if not self._root_folder_id:
            print("Creating root folder: MangaDex-Downloader")
            self._root_folder_id = self._create_folder_sync(ROOT_FOLDER_NAME)
        else:
            print(f"Found existing root folder: {self._root_folder_id}")

        sub_folders = self._get_sub_folders(
            self._root_folder_id, page_size=DEFAULT_SUB_FOLDER_PAGE_SIZE
        )

        cached_count = len(sub_folders)
        for folder in sub_folders:
            self._folder_cache[folder["name"]] = folder["id"]

        print(f"Cached {cached_count} manga folders")

        return self._root_folder_id

    def _get_root_folders(
        self, page_size: int | None = None
    ) -> list[GoogleDriveDirectory]:
        """List all folders in My Drive.

        Args:
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[GoogleDriveDirectory]: List of folder dictionaries with 'id' and 'name' keys
        """
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = (
            self._service.files()
            .list(
                q=query,
                spaces="drive",  # "drive" space is the root folder
                fields="files(id, name)",
                pageSize=page_size,
            )
            .execute()
        )

        return results.get("files", [])

    def _get_sub_folders(
        self, parent_id: str, page_size: int | None = None
    ) -> list[GoogleDriveDirectory]:
        """List all subfolders under a specific folder by parent ID.

        Args:
            parent_id: The ID of the parent folder
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[GoogleDriveDirectory]: List of folder dictionaries with 'id' and 'name' keys
        """
        query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = (
            self._service.files()
            .list(
                q=query,
                fields="files(id, name)",
                pageSize=page_size,
            )
            .execute()
        )

        return results.get("files", [])

    def _create_folder_sync(self, name: str, parent_id: str | None = None) -> str:
        """Create a new folder in Google Drive.

        Args:
            name: The name of the folder to create
            parent_id: The ID of the parent folder. If None, creates in My Drive root

        Returns:
            str: The ID of the created folder
        """
        metadata: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = self._service.files().create(body=metadata).execute()

        return folder["id"]

    async def get_or_create_manga_folder(self, manga_title: str) -> str:
        """Get or create a folder for a manga title.

        Checks the cache first, then creates the folder in Google Drive if needed.

        Args:
            manga_title: The title of the manga

        Returns:
            str: The ID of the folder

        Raises:
            RuntimeError: If the client has not been initialized
        """
        if manga_title in self._folder_cache:
            return self._folder_cache[manga_title]

        if not self._root_folder_id:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        folder_id = await asyncio.to_thread(
            self._create_folder_sync, manga_title, self._root_folder_id
        )
        self._folder_cache[manga_title] = folder_id

        return folder_id

    def _upload_file_sync(
        self,
        file_data: bytes,
        file_name: str,
        folder_id: str,
        mimetype: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        attempts: int = 1,
    ) -> str | None:
        """Upload a file to Google Drive (synchronous).

        Handles file conflicts by retrying with modified filenames.

        Args:
            file_data: The file data to upload
            file_name: The name of the file
            folder_id: The ID of the destination folder
            mimetype: The MIME type of the file
            chunk_size: The chunk size for resumable upload (default: 5MB)
            attempts: Current attempt number for recursive retries in name collision (default: 1)

        Returns:
            str: The ID of the uploaded file
        """
        name = Path(file_name).stem
        extension = Path(file_name).suffix

        file_metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=True,
            chunksize=chunk_size,
        )

        try:
            file = (
                self._service.files()
                .create(body=file_metadata, media_body=media)
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
                        chunk_size,
                        attempts + 1,
                    )
                logger.error(
                    "Upload failed: max retries exceeded due to file conflicts for %s",
                    file_name,
                )

            if e.resp.status == 429:
                logger.error(
                    "Upload failed: rate limit exceeded after internal retries for %s",
                    file_name,
                )
                raise RateLimitError(f"Rate limit exceeded: {file_name}") from e

            raise

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        folder_id: str,
        mimetype: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> str | None:
        """Upload a file to Google Drive (asynchronous).

        Args:
            file_data: The file data to upload
            file_name: The name of the file
            folder_id: The ID of the destination folder
            mimetype: The MIME type of the file
            chunk_size: The chunk size for resumable upload (default: 5MB)

        Returns:
            str | None: The ID of the uploaded file, or None if upload failed
        """
        return await asyncio.to_thread(
            self._upload_file_sync,
            file_data,
            file_name,
            folder_id,
            mimetype,
            chunk_size,
        )
