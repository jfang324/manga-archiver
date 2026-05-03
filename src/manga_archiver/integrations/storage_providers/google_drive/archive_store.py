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
    GoogleDriveFile,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
    InitResult,
)


class GoogleDriveArchiveStore:
    """Google Drive-backed store for manga archive operations."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        folder_cache: GoogleDriveFolderCache | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._sdk_client = GoogleDriveSdkClient(stored_token, max_retries)
        self._folder_cache = folder_cache if folder_cache is not None else GoogleDriveFolderCache()

    def initialize(self) -> InitResult:
        """Initialize root folder and hydrate the manga folder cache."""
        root_folders = self._sdk_client.list_root_folders(
            ROOT_FOLDER_NAME, page_size=DEFAULT_ROOT_PAGE_SIZE
        )

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

        sub_folders = self._sdk_client.list_sub_folders(
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

    def get_archived_chapter_numbers(
        self, manga_title: str, source: str, page_size: int = 1000
    ) -> list[float]:
        """Return archived chapter numbers for a cached manga folder."""
        folder_id = self._folder_cache.get_folder_id(source, manga_title)
        if not folder_id:
            return []

        files = self._sdk_client.list_files_in_folder(folder_id, page_size)
        return self._parse_chapter_numbers(files)

    async def upload_chapter(
        self,
        file_data: bytes,
        file_name: str,
        manga_title: str,
        source: str,
        chapter_num: str,
        chapter_title: str,
        mimetype: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> str | None:
        """Upload an archived manga chapter."""
        folder_id = await self._get_or_create_manga_folder(manga_title, source)
        file_metadata = GoogleDriveFileMetadata(
            source=source,
            chapter_num=chapter_num,
            chapter_title=chapter_title,
        )

        return await self._sdk_client.upload_file(
            file_data,
            file_name,
            folder_id,
            mimetype,
            file_metadata.to_app_properties(),
            chunk_size,
        )

    async def _get_or_create_manga_folder(self, manga_title: str, source: str) -> str:
        cached_folder_id = self._folder_cache.get_folder_id(source, manga_title)
        if cached_folder_id:
            return cached_folder_id

        if not self._folder_cache.root_folder_id:
            raise ClientNotInitializedError(
                "Archive store not initialized. Call initialize() first."
            )

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

    def _parse_chapter_numbers(self, files: list[GoogleDriveFile]) -> list[float]:
        chapter_numbers: list[float] = []

        for file in files:
            app_props = file.get("appProperties")
            if not app_props:
                continue

            chapter_num = app_props.get("chapter_num")
            if chapter_num is None:
                continue

            try:
                chapter_numbers.append(float(chapter_num))
            except (ValueError, TypeError):
                continue

        return chapter_numbers
