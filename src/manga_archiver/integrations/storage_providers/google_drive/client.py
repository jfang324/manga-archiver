from .constants import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_ROOT_PAGE_SIZE,
    DEFAULT_SUB_FOLDER_PAGE_SIZE,
    ROOT_FOLDER_NAME,
    SYSTEM_SOURCE,
)
from .folder_cache import GoogleDriveFolderCache
from .sdk_client import GoogleDriveSdkClient
from .types import (
    ClientNotInitializedError,
    GoogleApiStoredToken,
    GoogleDriveDirectory,
    GoogleDriveFile,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
    InitResult,
)


class GoogleDriveClient:
    """Client for interacting with Google Drive API for cloud storage. Must call initialize() after construction before using other methods."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        max_retries: int = DEFAULT_MAX_RETRIES,
        folder_cache: GoogleDriveFolderCache | None = None,
    ) -> None:
        """Initialize the Google Drive client.

        Args:
            stored_token: The token stored by the corresponding auth util
            max_retries: Maximum number of retries for failed uploads (default: 5)
            folder_cache: Shared Google Drive folder cache
        """
        self._sdk_client = GoogleDriveSdkClient(stored_token, max_retries)
        self._folder_cache = folder_cache if folder_cache is not None else GoogleDriveFolderCache()

    def initialize(self) -> InitResult:
        """Initialize and cache folders from Google Drive.

        Searches for the root Manga-Archiver folder, creates it if not
        found, then caches all existing manga subfolders.

        Returns:
            InitResult: Information about the initialization including root folder ID,
            cached folder count, and whether the root folder was created.
        """
        root_folders = self._get_root_folders(page_size=DEFAULT_ROOT_PAGE_SIZE)

        was_created = False
        for folder in root_folders:
            if folder["name"] == ROOT_FOLDER_NAME:
                self._folder_cache.root_folder_id = folder["id"]
                break

        if not self._folder_cache.root_folder_id:
            root_metadata = GoogleDriveFolderMetadata(source=SYSTEM_SOURCE)
            # TODO: Use async SDK folder creation after initialize() can become async.  # noqa: FIX002
            self._folder_cache.root_folder_id = self._sdk_client._create_folder_sync(
                ROOT_FOLDER_NAME, folder_metadata=root_metadata
            )
            was_created = True

        sub_folders = self._get_sub_folders(
            self._folder_cache.root_folder_id, page_size=DEFAULT_SUB_FOLDER_PAGE_SIZE
        )

        cached_count = 0
        for folder in sub_folders:
            app_props = folder.get("appProperties", {})
            if not app_props:
                continue

            try:
                metadata = GoogleDriveFolderMetadata.from_app_properties(app_props)
            except ValueError:
                continue

            self._folder_cache.set_folder_id(metadata.source, folder["name"], folder["id"])
            cached_count += 1

        return InitResult(
            root_folder_id=self._folder_cache.root_folder_id,
            cached_folder_count=cached_count,
            was_created=was_created,
        )

    def _get_root_folders(self, page_size: int | None = None) -> list[GoogleDriveDirectory]:
        """List all folders in My Drive.

        Args:
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[GoogleDriveDirectory]: List of folder dictionaries with 'id' and 'name' keys
        """
        return self._sdk_client.list_root_folders(ROOT_FOLDER_NAME, page_size)

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
        return self._sdk_client.list_sub_folders(parent_id, page_size)

    def get_files_in_folder(
        self, folder_id: str, page_size: int | None = None
    ) -> list[GoogleDriveFile]:
        """List all files in a specific folder.

        Args:
            folder_id: The ID of the folder to list files from
            page_size: Maximum number of results to return (default: None)

        Returns:
            list[GoogleDriveFile]: List of files with 'id', 'name', 'appProperties' keys
        """
        return self._sdk_client.list_files_in_folder(folder_id, page_size)

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
            ClientNotInitializedError: If the client has not been initialized
        """
        cached_folder_id = self._folder_cache.get_folder_id(source, manga_title)
        if cached_folder_id:
            return cached_folder_id

        if not self._folder_cache.root_folder_id:
            raise ClientNotInitializedError("Client not initialized. Call initialize() first.")

        async with self._folder_cache.lock:
            cached_folder_id = self._folder_cache.get_folder_id(source, manga_title)
            if cached_folder_id:
                return cached_folder_id

            existing_id = await self._sdk_client.search_folder_by_name(
                manga_title,
                self._folder_cache.root_folder_id,
                source,
            )

            if existing_id:
                self._folder_cache.set_folder_id(source, manga_title, existing_id)
                return existing_id

            folder_metadata = GoogleDriveFolderMetadata(source=source)
            folder_id = await self._sdk_client.create_folder(
                manga_title,
                folder_metadata,
                self._folder_cache.root_folder_id,
            )
            self._folder_cache.set_folder_id(source, manga_title, folder_id)

        return folder_id

    def get_cached_manga_folder_id(self, manga_title: str, source: str) -> str | None:
        """Get the folder ID for a manga title from the cache.

        Args:
            manga_title: The manga title to look up
            source: The content source (e.g., "mangadex")

        Returns:
            str | None: The folder ID if found in cache, None otherwise
        """
        return self._folder_cache.get_folder_id(source, manga_title)

    def _update_folder_metadata(self, folder_id: str, metadata: GoogleDriveFolderMetadata) -> None:
        """Update folder metadata with appProperties.

        Args:
            folder_id: The ID of the folder to update
            metadata: The folder metadata to apply
        """

        self._sdk_client.update_metadata(folder_id, metadata.to_app_properties())

    def _update_file_metadata(self, file_id: str, metadata: GoogleDriveFileMetadata) -> None:
        """Update file metadata with appProperties.

        Args:
            file_id: The ID of the file to update
            metadata: The file metadata to apply
        """

        self._sdk_client.update_metadata(file_id, metadata.to_app_properties())

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
            chunk_size: The chunk size for resumable upload (default: 16MB)

        Returns:
            str | None: The ID of the uploaded file, or None if API response missing ID

        Raises:
            ApiError: If max retries exceeded due to file conflicts
        """
        return await self._sdk_client.upload_file(
            file_data,
            file_name,
            folder_id,
            mimetype,
            file_metadata.to_app_properties(),
            chunk_size,
        )
