import logging
import sys

from .app import MangaDexDownloaderApp
from .cli import parse_args
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .pipeline_manager import PipelineConfig
from .repositories import FavoriteRepository
from .utils import load_settings, setup_logging
from .utils.auth.google_drive import handle_auth_login, handle_auth_logout, load_token

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the MangaDex Downloader CLI.

    Parses command-line arguments, initializes the Google Drive client
    if in archive mode, and launches the Textual UI application.
    """
    setup_logging()

    try:
        args = parse_args()
    except SystemExit:
        raise

    if hasattr(args, "command") and args.command == "auth":
        if args.subcommand == "login":
            sys.exit(handle_auth_login())

        elif args.subcommand == "logout":
            sys.exit(handle_auth_logout())

        else:
            logger.error("Please specify 'auth login' or 'auth logout'")
            sys.exit(1)

    google_drive_client = None

    if args.archive:
        token = load_token()

        if token is None:
            print(
                "Archive mode requires authentication. Run: mangadex-downloader auth login"
            )
            sys.exit(1)

        try:
            google_drive_client = GoogleDriveClient(token)
            google_drive_client.initialize()
        except Exception as e:
            logger.error("Failed to initialize Google Drive: %s", e)
            print(
                "Failed to initialize Google Drive. Run: mangadex-downloader auth logout && auth login"
            )
            sys.exit(1)

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
    except Exception as e:
        logger.error("Failed to load configs: %s", e)
        sys.exit(1)

    favorite_repository = FavoriteRepository()

    app = MangaDexDownloaderApp(
        pipeline_config=pipeline_config,
        app_config=app_config,
        favorite_repository=favorite_repository,
        google_drive_client=google_drive_client,
    )
    app.run()


if __name__ == "__main__":
    main()
