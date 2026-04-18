import asyncio
import logging
import sys
from argparse import Namespace

from .app import MangaArchiverApp
from .backlog_sync import BacklogSync
from .cli import parse_args
from .constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_INIT_ERROR,
    EXIT_MIGRATION_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from .db.migrations import DEFAULT_GOOGLE_DRIVE_VERSION
from .db.schema_manager import MigrationError, SchemaManager
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .pipeline_manager import PipelineConfig
from .repositories import FavoriteRepository
from .utils import load_settings, setup_logging
from .utils.auth.google_drive import handle_auth_login, handle_auth_logout, load_token

logger = logging.getLogger(__name__)


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


def main() -> None:
    """Provide CLI entry point for MangaDex Downloader.

    Parses command-line arguments, initializes the Google Drive client
    if in archive mode, and launches the Textual UI application.
    """
    setup_logging()
    args = parse_args()
    schema_manager = SchemaManager()

    handled, exit_code = _handle_auth(args)
    if handled:
        sys.exit(exit_code)

    handled, exit_code = _handle_migrations(args, schema_manager)
    if handled:
        sys.exit(exit_code)

    google_drive_enabled = args.archive

    try:
        is_valid, error_msg = schema_manager.check_versions(google_drive_enabled)
    except MigrationError as e:
        logger.error("Failed to check database versions: %s", e)
        sys.exit(EXIT_VALIDATION_ERROR)

    if not is_valid:
        print(error_msg)
        sys.exit(EXIT_VALIDATION_ERROR)

    google_drive_client = None

    if google_drive_enabled:
        token = load_token()

        if token is None:
            print("Archive mode requires authentication. Run: manga-archiver auth login")
            sys.exit(EXIT_AUTH_ERROR)

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
            print(
                "Failed to write Google Drive version record. Run: manga-archiver migrate google-drive"
            )
            sys.exit(EXIT_INIT_ERROR)
        except Exception as e:
            logger.error("Failed to initialize Google Drive: %s", e)
            print(
                "Failed to initialize Google Drive. Run: manga-archiver auth logout && auth login"
            )
            sys.exit(EXIT_INIT_ERROR)

    try:
        pipeline_config = PipelineConfig(
            num_resolve_workers=args.resolve_workers,
            num_download_workers=args.download_workers,
            num_merge_workers=args.merge_workers,
            resolve_rate_limit=args.resolve_rate_limit,
            download_rate_limit=args.download_rate_limit,
            benchmark_enabled=args.benchmark,
        )

        app_config = load_settings()
        favorite_repository = FavoriteRepository()

        backlog = None
        if args.backlog:
            if not google_drive_client:
                print("--backlog requires a Google Drive client, try running with --archive")
                sys.exit(EXIT_INIT_ERROR)

            backlog_sync = BacklogSync(
                favorite_repository=favorite_repository,
                google_drive_client=google_drive_client,
                output_directory=app_config.output_path,
                output_format=str(app_config.output_format),
            )
            backlog = asyncio.run(backlog_sync.run())

    except Exception as e:
        logger.error("Failed to initialize: %s", e)
        sys.exit(EXIT_INIT_ERROR)

    app = MangaArchiverApp(
        pipeline_config=pipeline_config,
        app_config=app_config,
        favorite_repository=favorite_repository,
        google_drive_client=google_drive_client,
        backlog=backlog,
        auto_exit=args.auto_exit,
    )
    app.run()


if __name__ == "__main__":
    main()
