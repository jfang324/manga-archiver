import asyncio
import io
import logging
from dataclasses import dataclass
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
    SYSTEM_SOURCE,
)
from .types import (
    GoogleApiStoredToken,
    GoogleDriveDirectory,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MangaFolderKey:
    source: str
    title: str


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
        self._folder_cache: dict[_MangaFolderKey, str] = {}
        self._max_retries = max_retries

    def initialize(self) -> str:
        """Initialize and cache folders from Google Drive.

        Searches for the root Manga-Archiver folder, creates it if not
        found, then caches all existing manga subfolders.

        Returns:
            str: The ID of the root folder
        """
        # initialize is meant to be called before the app starts, so we use print for visual feedback
        print("Initializing Google Drive...")

        root_folders = self._get_root_folders(page_size=DEFAULT_ROOT_PAGE_SIZE)

        for folder in root_folders:
            if folder["name"] == ROOT_FOLDER_NAME:
                self._root_folder_id = folder["id"]
                break

        if not self._root_folder_id:
            print(f"Creating root folder: {ROOT_FOLDER_NAME}")
            root_metadata = GoogleDriveFolderMetadata(source=SYSTEM_SOURCE)
            self._root_folder_id = self._create_folder_sync(
                ROOT_FOLDER_NAME, folder_metadata=root_metadata
            )
        else:
            print(f"Found existing root folder: {self._root_folder_id}")

        sub_folders = self._get_sub_folders(
            self._root_folder_id, page_size=DEFAULT_SUB_FOLDER_PAGE_SIZE
        )

        cached_count = 0
        for folder in sub_folders:
            app_props = folder.get("appProperties")
            if not app_props or not app_props.get("source"):
                logger.debug("Folder '%s' has no source metadata, skipping cache", folder["name"])
                continue

            source = app_props["source"]
            cache_key = _MangaFolderKey(source, folder["name"])
            self._folder_cache[cache_key] = folder["id"]
            cached_count += 1

        # Log files without metadata for debugging
        for folder in sub_folders:
            files = self.get_files_in_folder(folder["id"])
            for f in files:
                file_props = f.get("appProperties")
                if not file_props or not file_props.get("source"):
                    logger.debug(
                        "File '%s' in folder '%s' has no source metadata",
                        f["name"],
                        folder["name"],
                    )

        print(f"Cached {cached_count} manga folders")

        return self._root_folder_id

    def _get_root_folders(self, page_size: int | None = None) -> list[GoogleDriveDirectory]:
        """List all folders in My Drive.

        Args:
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[GoogleDriveDirectory]: List of folder dictionaries with 'id' and 'name' keys
        """
        query = f"name='{ROOT_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = (
            self._service.files()
            .list(
                q=query,
                spaces="drive",  # "drive" space is the root folder
                fields="files(id, name, appProperties)",
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
                fields="files(id, name, appProperties)",
                pageSize=page_size,
            )
            .execute()
        )

        return results.get("files", [])

    def get_files_in_folder(self, folder_id: str, page_size: int | None = None) -> list[dict]:
        """List all files in a specific folder.

        Args:
            folder_id: The ID of the folder to list files from
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[dict]: List of file dictionaries with 'id' and 'name' keys
        """
        query = f"'{folder_id}' in parents and trashed=false"

        results = (
            self._service.files()
            .list(
                q=query,
                fields="files(id, name, appProperties)",
                pageSize=page_size,
            )
            .execute()
        )

        return results.get("files", [])

    def _create_folder_sync(
        self,
        name: str,
        folder_metadata: GoogleDriveFolderMetadata,
        parent_id: str | None = None,
    ) -> str:
        """Create a new folder in Google Drive.

        Args:
            name: The name of the folder to create
            folder_metadata: Metadata for the folder
            parent_id: The ID of the parent folder. If None, creates in My Drive root

        Returns:
            str: The ID of the created folder
        """
        file_metadata: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "appProperties": folder_metadata.to_app_properties(),
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        folder = self._service.files().create(body=file_metadata).execute()

        return folder["id"]

    async def get_or_create_manga_folder(self, manga_title: str, source: str) -> str:
        """Get or create a folder for a manga title.

        Checks the cache first, searches Google Drive if not found in cache,
        then creates the folder if neither cache nor search finds it.

        Args:
            manga_title: The title of the manga
            source: The content source (e.g., "mangadex")

        Returns:
            str: The ID of the folder

        Raises:
            RuntimeError: If the client has not been initialized
        """
        cache_key = _MangaFolderKey(source, manga_title)

        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        if not self._root_folder_id:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        existing_id = await asyncio.to_thread(
            self._search_folder_by_name, manga_title, self._root_folder_id, source
        )

        if existing_id:
            self._folder_cache[cache_key] = existing_id
            return existing_id

        folder_metadata = GoogleDriveFolderMetadata(source=source)
        folder_id = await asyncio.to_thread(
            self._create_folder_sync, manga_title, folder_metadata, self._root_folder_id
        )
        self._folder_cache[cache_key] = folder_id

        return folder_id

    def get_manga_folder_id(self, manga_title: str, source: str) -> str | None:
        """Get the folder ID for a manga title from the cache.

        Args:
            manga_title: The manga title to look up
            source: The content source (e.g., "mangadex")

        Returns:
            str | None: The folder ID if found in cache, None otherwise
        """
        cache_key = _MangaFolderKey(source, manga_title)
        return self._folder_cache.get(cache_key)

    def _search_folder_by_name(self, name: str, parent_id: str, source: str) -> str | None:
        """Search for a folder by name within a parent folder.

        Args:
            name: The folder name to search for
            parent_id: The ID of the parent folder
            source: The content source to match

        Returns:
            str | None: Folder ID if found, None otherwise
        """
        query = (
            f"name='{name}' and '{parent_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and trashed=false and "
            f"appProperties has {{ key='source' and value='{source}' }}"
        )

        results = (
            self._service.files()
            .list(
                q=query,
                fields="files(id, name, appProperties)",
                pageSize=1,
            )
            .execute()
        )

        files = results.get("files", [])
        return files[0]["id"] if files else None

    def _update_folder_metadata(self, folder_id: str, metadata: GoogleDriveFolderMetadata) -> None:
        """Update folder metadata with appProperties.

        Args:
            folder_id: The ID of the folder to update
            metadata: The folder metadata to apply
        """
        try:
            self._service.files().update(
                fileId=folder_id,
                body={"appProperties": metadata.to_app_properties()},
            ).execute()
        except Exception as e:
            logger.error("Failed to update folder %s metadata: %s", folder_id, e)

    def _update_file_metadata(self, file_id: str, metadata: GoogleDriveFileMetadata) -> None:
        """Update file metadata with appProperties.

        Args:
            file_id: The ID of the file to update
            metadata: The file metadata to apply
        """
        try:
            self._service.files().update(
                fileId=file_id,
                body={"appProperties": metadata.to_app_properties()},
            ).execute()
        except Exception as e:
            logger.error("Failed to update file %s metadata: %s", file_id, e)

    def _upload_file_sync(
        self,
        file_data: bytes,
        file_name: str,
        folder_id: str,
        mimetype: str,
        file_metadata: GoogleDriveFileMetadata,
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
            file_metadata: Metadata for the file

        Returns:
            str: The ID of the uploaded file
        """
        name = Path(file_name).stem
        extension = Path(file_name).suffix

        upload_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "appProperties": file_metadata.to_app_properties(),
        }

        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=True,
            chunksize=chunk_size,
        )

        try:
            file = self._service.files().create(body=upload_metadata, media_body=media).execute()

            return file.get("id")
        except HttpError as e:
            if e.resp.status == 409:
                if attempts < self._max_retries:
                    return self._upload_file_sync(
                        file_data,
                        f"{name} ({attempts}){extension}",
                        folder_id,
                        mimetype,
                        file_metadata,
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
        file_metadata: GoogleDriveFileMetadata,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> str | None:
        """Upload a file to Google Drive (asynchronous).

        Args:
            file_data: The file data to upload
            file_name: The name of the file
            folder_id: The ID of the destination folder
            mimetype: The MIME type of the file
            file_metadata: Metadata for the file
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
            file_metadata,
            chunk_size,
            1,  # attempts
        )
