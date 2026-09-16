import logging
from argparse import Namespace
from dataclasses import dataclass

import aiohttp

from .app import MangaArchiverApp
from .backlog_sync import BacklogSync
from .cli.presets import RuntimePreset, get_preset
from .constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_INIT_ERROR,
    EXIT_VALIDATION_ERROR,
)
from .db.migrations import DEFAULT_GOOGLE_DRIVE_VERSION
from .db.schema_manager import MigrationError, SchemaManager
from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import (
    GoogleDriveArchiveStore,
    GoogleDriveFolderCache,
)
from .integrations.webhooks import WebhookClient
from .models.app_config import AppConfig
from .persistence import (
    GoogleDriveTokenStore,
    ResumableJobStore,
    SettingsStore,
    WebhookConfigStore,
)
from .persistence.google_drive_token_store import GoogleApiStoredToken
from .pipeline import PipelineConfig, PipelineManager
from .repositories import FavoriteRepository
from .utils import DownloadClient
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoogleDriveInitResult:
    """Result of Google Drive initialization."""

    archive_store: GoogleDriveArchiveStore | None = None
    folder_cache: GoogleDriveFolderCache | None = None
    token: GoogleApiStoredToken | None = None
    exit_code: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class BacklogSyncResult:
    """Result of backlog sync."""

    backlog: list[FetchingResourcesJob] | None = None
    exit_code: int | None = None
    message: str | None = None


def validate_schema_versions(
    schema_manager: SchemaManager, google_drive_enabled: bool
) -> tuple[int, str] | None:
    """Validate schema versions before application startup.

    Returns:
        tuple[int, str] | None: A tuple containing the exit code and error message on failure, or None on success.
    """
    try:
        is_valid, error_msg = schema_manager.check_versions(google_drive_enabled)
    except MigrationError as e:
        logger.error("Failed to check database versions: %s", e)
        return EXIT_VALIDATION_ERROR, "Failed to check database versions."

    if not is_valid:
        return EXIT_VALIDATION_ERROR, error_msg

    return None


async def initialize_google_drive(
    schema_manager: SchemaManager,
    google_drive_token_store: GoogleDriveTokenStore,
) -> GoogleDriveInitResult:
    """Initialize Google Drive client for archive mode."""
    token = await google_drive_token_store.load()

    if token is None:
        return GoogleDriveInitResult(
            exit_code=EXIT_AUTH_ERROR,
            message=(
                "Archive mode requires authentication. Run: manga-archiver auth google-drive login"
            ),
        )

    try:
        google_drive_folder_cache = GoogleDriveFolderCache()
        google_drive_archive_store = GoogleDriveArchiveStore(
            token, folder_cache=google_drive_folder_cache
        )

        print("Initializing Google Drive...")
        init_result = await google_drive_archive_store.initialize()

        if init_result.was_created:
            print(f"Created root folder: {init_result.root_folder_id}")

        print(f"Cached {init_result.cached_folder_count} manga folders")

        schema_manager.insert_version_record("google_drive", DEFAULT_GOOGLE_DRIVE_VERSION)
    except MigrationError as e:
        logger.error("Failed to insert %s version record: %s", "google_drive", e)
        return GoogleDriveInitResult(
            exit_code=EXIT_INIT_ERROR,
            message=(
                "Failed to write Google Drive version record. "
                "Run: manga-archiver migrate google-drive"
            ),
        )
    except Exception as e:
        logger.error("Failed to initialize Google Drive: %s", e)
        return GoogleDriveInitResult(
            exit_code=EXIT_INIT_ERROR,
            message=(
                "Failed to initialize Google Drive. "
                "Run: manga-archiver auth google-drive logout && "
                "manga-archiver auth google-drive login"
            ),
        )

    return GoogleDriveInitResult(
        archive_store=google_drive_archive_store,
        folder_cache=google_drive_folder_cache,
        token=token,
    )


def build_persistence_stores() -> tuple[
    ResumableJobStore,
    SettingsStore,
    WebhookConfigStore,
    GoogleDriveTokenStore,
]:
    """Build persistence stores."""
    return ResumableJobStore(), SettingsStore(), WebhookConfigStore(), GoogleDriveTokenStore()


async def build_configurations(
    args: Namespace, settings_store: SettingsStore
) -> tuple[PipelineConfig, AppConfig]:
    """Build startup configuration objects."""
    preset = get_runtime_preset(args)
    pipeline_config = PipelineConfig(
        num_resolve_workers=preset.resolve_workers,
        num_download_workers=preset.download_workers,
        num_merge_workers=preset.merge_workers,
        num_upload_workers=preset.upload_workers,
        resolve_rate_limit=preset.resolve_rate_limit,
        download_rate_limit=preset.download_rate_limit,
        resolve_queue_size=preset.queue_size,
        download_queue_size=preset.queue_size * 2,
        merge_queue_size=preset.queue_size,
        upload_queue_size=preset.queue_size,
        benchmark_enabled=args.benchmark,
    )
    app_config = await settings_store.load()

    return pipeline_config, app_config


def get_runtime_preset(args: Namespace) -> RuntimePreset:
    """Return the selected runtime preset or the default preset."""
    return get_preset(args.preset)


def create_client_session() -> aiohttp.ClientSession:
    """Create and return the shared HTTP client session as a context manager."""
    # Session needs TCPConnector with ThreadedResolver for aiodns (avoids 443 errors)
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    )


async def build_async_dependencies(
    session: aiohttp.ClientSession,
    args: Namespace,
    webhook_config_store: WebhookConfigStore,
) -> tuple[ContentProviderManager, DownloadClient, WebhookClient]:
    """Build session-bound async dependencies."""
    preset = get_runtime_preset(args)
    provider_manager = ContentProviderManager(
        session,
        preset.resolve_rate_limit,
        preset.download_rate_limit,
    )
    download_client = DownloadClient(session)
    webhook_config = await webhook_config_store.load()
    providers = webhook_config_store.get_enabled_webhooks(webhook_config)
    webhook_client = WebhookClient(
        session=session,
        providers=providers,
        config=webhook_config,
    )

    return provider_manager, download_client, webhook_client


def build_app(
    app_config: AppConfig,
    pipeline_manager: PipelineManager,
    favorite_repository: FavoriteRepository,
    provider_manager: ContentProviderManager,
    settings_store: SettingsStore,
    backlog: list[FetchingResourcesJob] | None,
    resumable_jobs: list[FetchingResourcesJob] | None,
) -> MangaArchiverApp:
    """Build the Textual application instance."""
    return MangaArchiverApp(
        app_config=app_config,
        pipeline_manager=pipeline_manager,
        favorite_repository=favorite_repository,
        provider_manager=provider_manager,
        settings_store=settings_store,
        backlog=backlog,
        resumable_jobs=resumable_jobs,
    )


async def load_backlog(
    args: Namespace,
    favorite_repository: FavoriteRepository,
    google_drive_archive_store: GoogleDriveArchiveStore | None,
    provider_manager: ContentProviderManager,
    app_config: AppConfig,
) -> BacklogSyncResult:
    """Load backlog jobs from Google Drive + provider APIs."""
    if not args.backlog:
        return BacklogSyncResult(backlog=[])

    if not google_drive_archive_store:
        return BacklogSyncResult(
            exit_code=EXIT_INIT_ERROR,
            message="--backlog requires a Google Drive archive store, try running with --archive",
        )

    backlog_sync = BacklogSync(
        favorite_repository=favorite_repository,
        google_drive_archive_store=google_drive_archive_store,
        provider_manager=provider_manager,
        app_config=app_config,
    )

    backlog = await backlog_sync.run()
    return BacklogSyncResult(backlog=backlog)
