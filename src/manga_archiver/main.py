import asyncio
import logging
import sys
from argparse import Namespace
from dataclasses import dataclass

import aiohttp

from .app import MangaArchiverApp
from .backlog_sync import BacklogSync
from .cli import parse_args
from .constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_INIT_ERROR,
    EXIT_MIGRATION_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from .db.migrations import DEFAULT_GOOGLE_DRIVE_VERSION
from .db.schema_manager import MigrationError, SchemaManager
from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .models.app_config import AppConfig
from .pipeline_manager import PipelineConfig
from .repositories import FavoriteRepository
from .utils import DownloadClient, setup_logging
from .utils.auth.google_drive import handle_auth_login, handle_auth_logout, load_token
from .utils.settings_manager import load_settings
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoogleDriveInitResult:
    """Result of Google Drive initialization."""

    client: GoogleDriveClient | None = None
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
    setup_logging()
    args = parse_args()
    schema_manager = SchemaManager()

    exit_code = _handle_subcommands(args, schema_manager)
    if exit_code is not None:
        sys.exit(exit_code)

    google_drive_enabled = args.archive
    validation_result = _validate_schema_versions(schema_manager, google_drive_enabled)
    if validation_result is not None:
        exit_code, message = validation_result
        print(message)
        sys.exit(exit_code)

    google_drive_client = None

    if google_drive_enabled:
        init_result = _initialize_google_drive(schema_manager)
        if init_result.message is not None:
            print(init_result.message)

        if init_result.exit_code is not None:
            sys.exit(init_result.exit_code)

        google_drive_client = init_result.client

    try:
        pipeline_config, app_config = _build_configurations(args)
        favorite_repository = FavoriteRepository()

        async with _create_client_session() as session:
            provider_manager, download_client = _build_async_dependencies(session, args)
            backlog_result = await _load_backlog(
                args=args,
                favorite_repository=favorite_repository,
                google_drive_client=google_drive_client,
                provider_manager=provider_manager,
                app_config=app_config,
            )

            if backlog_result.exit_code is not None:
                print(backlog_result.message)
                sys.exit(backlog_result.exit_code)

            backlog = backlog_result.backlog

            app = _build_app(
                pipeline_config=pipeline_config,
                app_config=app_config,
                favorite_repository=favorite_repository,
                google_drive_client=google_drive_client,
                backlog=backlog,
                provider_manager=provider_manager,
                download_client=download_client,
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


def _handle_subcommands(args: Namespace, schema_manager: SchemaManager) -> int | None:
    """Handle CLI subcommands before normal app startup.

    Returns:
        int | None: An exit code if the command was handled, None if not
    """
    handled, exit_code = _handle_auth(args)
    if handled:
        return exit_code

    handled, exit_code = _handle_migrations(args, schema_manager)
    if handled:
        return exit_code

    return None


def _handle_auth(args: Namespace) -> tuple[bool, int]:
    """Handle authentication commands.

    Returns:
        tuple[bool, int]: Tuple of (handled, exit_code). If handled is False, caller should continue.
    """
    if args.command != "auth":
        return False, EXIT_SUCCESS

    if args.auth_command == "login":
        return True, handle_auth_login()

    if args.auth_command == "logout":
        return True, handle_auth_logout()

    return True, EXIT_AUTH_ERROR


def _handle_migrations(args: Namespace, schema_manager: SchemaManager) -> tuple[bool, int]:
    """Handle migration commands.

    Returns:
        tuple[bool, int]: Tuple of (handled, exit_code). If handled is False, caller should continue.
    """
    if args.command != "migrate":
        return False, EXIT_SUCCESS

    print("Running migrations...")

    try:
        if args.migrate_system == "database":
            system = "database"

        elif args.migrate_system == "google-drive":
            system = "google_drive"

        else:
            return True, EXIT_MIGRATION_ERROR

        result = schema_manager.run_migrations(system)
        print(f"  {result}")

        return True, EXIT_SUCCESS
    except Exception as e:
        print(f"Migration failed: {e}")
        return True, EXIT_MIGRATION_ERROR


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
        google_drive_client = GoogleDriveClient(token)

        print("Initializing Google Drive...")
        init_result = google_drive_client.initialize()

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

    return GoogleDriveInitResult(client=google_drive_client)


def _build_configurations(args: Namespace) -> tuple[PipelineConfig, AppConfig]:
    """Build startup configuration objects."""
    pipeline_config = PipelineConfig(
        num_resolve_workers=args.resolve_workers,
        num_download_workers=args.download_workers,
        num_merge_workers=args.merge_workers,
        resolve_rate_limit=args.resolve_rate_limit,
        download_rate_limit=args.download_rate_limit,
        benchmark_enabled=args.benchmark,
    )
    app_config = load_settings()

    return pipeline_config, app_config


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
    provider_manager = ContentProviderManager(
        session,
        resolve_rate_limit=args.resolve_rate_limit,
        download_rate_limit=args.download_rate_limit,
    )
    download_client = DownloadClient(session)

    return provider_manager, download_client


def _build_app(
    pipeline_config: PipelineConfig,
    app_config: AppConfig,
    favorite_repository: FavoriteRepository,
    google_drive_client: GoogleDriveClient | None,
    backlog: list[FetchingResourcesJob] | None,
    provider_manager: ContentProviderManager,
    download_client: DownloadClient,
    auto_exit: bool,
) -> MangaArchiverApp:
    """Build the Textual application instance."""
    return MangaArchiverApp(
        pipeline_config=pipeline_config,
        app_config=app_config,
        favorite_repository=favorite_repository,
        google_drive_client=google_drive_client,
        backlog=backlog,
        provider_manager=provider_manager,
        download_client=download_client,
        auto_exit=auto_exit,
    )


async def _load_backlog(
    args: Namespace,
    favorite_repository: FavoriteRepository,
    google_drive_client: GoogleDriveClient | None,
    provider_manager: ContentProviderManager,
    app_config: AppConfig,
) -> BacklogSyncResult:
    """Load backlog jobs from Google Drive + provider APIs.

    Returns:
        BacklogSyncResult: A tuple containing the exit code and error message on failure, or a list of backlog jobs on success.
    """
    if not args.backlog:
        return BacklogSyncResult(backlog=[])

    if not google_drive_client:
        return BacklogSyncResult(
            exit_code=EXIT_INIT_ERROR,
            message="--backlog requires a Google Drive client, try running with --archive",
        )

    backlog_sync = BacklogSync(
        favorite_repository=favorite_repository,
        google_drive_client=google_drive_client,
        provider_manager=provider_manager,
        output_directory=app_config.output_path,
        output_format=app_config.output_format,
    )

    backlog = await backlog_sync.run()
    return BacklogSyncResult(backlog=backlog)


if __name__ == "__main__":
    main()
