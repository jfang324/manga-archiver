import asyncio
import io
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

ROOT_FOLDER_NAME = "MangaDex-Downloader"
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
DEFAULT_ROOT_PAGE_SIZE = 1
DEFAULT_SUB_FOLDER_PAGE_SIZE = 1
DEFAULT_MAX_RETRIES = 5


class GoogleDriveClient:
    """Client for interacting with Google Drive API for cloud storage.

    Provides methods for folder management and file uploads to Google Drive.
    Must call initialize() after construction before using other methods.
    """

    def __init__(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        token_uri: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize the Google Drive client.

        Args:
            refresh_token: OAuth refresh token for authentication
            client_id: OAuth client ID
            client_secret: OAuth client secret
            token_uri: OAuth token endpoint URL
            max_retries: Maximum number of retries for failed uploads (default: 5)
        """
        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri=token_uri,
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
            The ID of the root folder

        Raises:
            Exception: If initialization fails
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

    def _get_root_folders(self, page_size: int | None = None) -> list[dict[str, str]]:
        """List all folders in My Drive (the "drive" space).

        Args:
            page_size: Maximum number of results to return (default: None)

        Returns:
            List of folder dictionaries with 'id' and 'name' keys
        """
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = (
            self._service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
                pageSize=page_size,
            )
            .execute()
        )
        return results.get("files", [])

    def _get_sub_folders(
        self, parent_id: str, page_size: int | None = None
    ) -> list[dict[str, str]]:
        """List all subfolders under a specific folder by parent ID.

        Args:
            parent_id: The ID of the parent folder
            page_size: Maximum number of results to return (default: None)

        Returns:
            List of folder dictionaries with 'id' and 'name' keys
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
            The ID of the created folder
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
            The ID of the folder

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
            attempts: Current attempt number for recursive retries (default: 1)

        Returns:
            The ID of the uploaded file, or None if upload failed
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
                return None
            logger.error("Upload failed: %s", e)
            return None

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
            The ID of the uploaded file, or None if upload failed
        """
        return await asyncio.to_thread(
            self._upload_file_sync,
            file_data,
            file_name,
            folder_id,
            mimetype,
            chunk_size,
        )
