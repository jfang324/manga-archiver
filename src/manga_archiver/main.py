import asyncio
import logging
import sys
from argparse import Namespace
from dataclasses import dataclass

import aiohttp

from .app import MangaArchiverApp
from .backlog_sync import BacklogSync
from .cli import parse_args
from .cli.handlers import handle_subcommands
from .cli.presets import RuntimePreset, get_preset
from .constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_INIT_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_VALIDATION_ERROR,
)
from .db.migrations import DEFAULT_GOOGLE_DRIVE_VERSION
from .db.schema_manager import MigrationError, SchemaManager
from .headless_runner import HeadlessPipelineRunner
from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import (
    GoogleDriveArchiveStore,
    GoogleDriveFolderCache,
)
from .integrations.storage_providers.google_drive.types import GoogleApiStoredToken
from .models.app_config import AppConfig
from .pipeline_manager import PipelineConfig, PipelineManager
from .repositories import FavoriteRepository
from .utils import DownloadClient, setup_logging
from .utils.auth.google_drive import load_token
from .utils.settings_manager import load_settings
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


def main() -> None:
    """CLI entry point - creates an event loop and runs the application."""
    asyncio.run(_async_main())


async def _async_main() -> None:
    """Set up dependencies and run the application."""
    args = parse_args()

    exit_code = handle_subcommands(args)
    if exit_code is not None:
        sys.exit(exit_code)

    setup_logging()
    schema_manager = SchemaManager()

    exit_code = handle_subcommands(args, schema_manager)
    if exit_code is not None:
        sys.exit(exit_code)

    google_drive_enabled = args.archive
    validation_result = _validate_schema_versions(schema_manager, google_drive_enabled)
    if validation_result is not None:
        exit_code, message = validation_result
        print(message)
        sys.exit(exit_code)

    google_drive_archive_store = None
    google_drive_folder_cache = None
    google_drive_token = None

    if google_drive_enabled:
        init_result = _initialize_google_drive(schema_manager)
        if init_result.message is not None:
            print(init_result.message)

        if init_result.exit_code is not None:
            sys.exit(init_result.exit_code)

        google_drive_archive_store = init_result.archive_store
        google_drive_folder_cache = init_result.folder_cache
        google_drive_token = init_result.token

    try:
        pipeline_config, app_config = _build_configurations(args)
        favorite_repository = FavoriteRepository()

        async with _create_client_session() as session:
            provider_manager, download_client = _build_async_dependencies(session, args)
            backlog_result = await _load_backlog(
                args=args,
                favorite_repository=favorite_repository,
                google_drive_archive_store=google_drive_archive_store,
                provider_manager=provider_manager,
                app_config=app_config,
            )

            if backlog_result.exit_code is not None:
                print(backlog_result.message)
                sys.exit(backlog_result.exit_code)

            backlog = backlog_result.backlog

            pipeline_manager = PipelineManager(
                provider_manager,
                download_client,
                pipeline_config,
                google_drive_token=google_drive_token,
                google_drive_folder_cache=google_drive_folder_cache,
            )

            if args.headless:
                exit_code = await HeadlessPipelineRunner(pipeline_manager).run(backlog)
                sys.exit(exit_code)

            app = _build_app(
                pipeline_manager=pipeline_manager,
                app_config=app_config,
                favorite_repository=favorite_repository,
                backlog=backlog,
                provider_manager=provider_manager,
                auto_exit=args.auto_exit,
            )

            try:
                await app.run_async()
            except Exception as e:
                logger.error("Runtime error during app execution: %s", e)
                sys.exit(EXIT_RUNTIME_ERROR)
    except Exception as e:
        logger.error("Failed to initialize: %s", e)
        sys.exit(EXIT_INIT_ERROR)


def _validate_schema_versions(
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


def _initialize_google_drive(schema_manager: SchemaManager) -> GoogleDriveInitResult:
    """Initialize Google Drive client for archive mode."""
    token = load_token()

    if token is None:
        return GoogleDriveInitResult(
            exit_code=EXIT_AUTH_ERROR,
            message="Archive mode requires authentication. Run: manga-archiver auth login",
        )

    try:
        google_drive_folder_cache = GoogleDriveFolderCache()
        google_drive_archive_store = GoogleDriveArchiveStore(
            token, folder_cache=google_drive_folder_cache
        )

        print("Initializing Google Drive...")
        init_result = google_drive_archive_store.initialize()

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
            message="Failed to initialize Google Drive. Run: manga-archiver auth logout && auth login",
        )

    return GoogleDriveInitResult(
        archive_store=google_drive_archive_store,
        folder_cache=google_drive_folder_cache,
        token=token,
    )


def _build_configurations(args: Namespace) -> tuple[PipelineConfig, AppConfig]:
    """Build startup configuration objects."""
    preset = _get_runtime_preset(args)
    pipeline_config = PipelineConfig(
        num_resolve_workers=preset.resolve_workers if preset else args.resolve_workers,
        num_download_workers=preset.download_workers if preset else args.download_workers,
        num_merge_workers=preset.merge_workers if preset else args.merge_workers,
        resolve_rate_limit=preset.resolve_rate_limit if preset else args.resolve_rate_limit,
        download_rate_limit=preset.download_rate_limit if preset else args.download_rate_limit,
        resolve_queue_size=preset.queue_size if preset else args.queue_size,
        download_queue_size=(preset.queue_size if preset else args.queue_size) * 2,
        merge_queue_size=preset.queue_size if preset else args.queue_size,
        upload_queue_size=preset.queue_size if preset else args.queue_size,
        benchmark_enabled=args.benchmark,
    )
    app_config = load_settings()

    return pipeline_config, app_config


def _get_runtime_preset(args: Namespace) -> RuntimePreset | None:
    """Return the selected runtime preset, if any."""
    if args.preset is None:
        return None

    return get_preset(args.preset)


def _create_client_session() -> aiohttp.ClientSession:
    """Create and return the shared HTTP client session as a context manager."""
    # Session needs TCPConnector with ThreadedResolver for aiodns (avoids 443 errors)
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    )


def _build_async_dependencies(
    session: aiohttp.ClientSession, args: Namespace
) -> tuple[ContentProviderManager, DownloadClient]:
    """Build session-bound async dependencies."""
    preset = _get_runtime_preset(args)
    provider_manager = ContentProviderManager(
        session,
        resolve_rate_limit=preset.resolve_rate_limit if preset else args.resolve_rate_limit,
        download_rate_limit=preset.download_rate_limit if preset else args.download_rate_limit,
    )
    download_client = DownloadClient(session)

    return provider_manager, download_client


def _build_app(
    pipeline_manager: PipelineManager,
    app_config: AppConfig,
    favorite_repository: FavoriteRepository,
    backlog: list[FetchingResourcesJob] | None,
    provider_manager: ContentProviderManager,
    auto_exit: bool,
) -> MangaArchiverApp:
    """Build the Textual application instance."""
    return MangaArchiverApp(
        pipeline_manager=pipeline_manager,
        app_config=app_config,
        favorite_repository=favorite_repository,
        backlog=backlog,
        provider_manager=provider_manager,
        auto_exit=auto_exit,
    )


async def _load_backlog(
    args: Namespace,
    favorite_repository: FavoriteRepository,
    google_drive_archive_store: GoogleDriveArchiveStore | None,
    provider_manager: ContentProviderManager,
    app_config: AppConfig,
) -> BacklogSyncResult:
    """Load backlog jobs from Google Drive + provider APIs.

    Returns:
        BacklogSyncResult: A tuple containing the exit code and error message on failure, or a list of backlog jobs on success.
    """
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


if __name__ == "__main__":
    main()
