import logging
import sys

from .app import MangaDexDownloaderApp
from .cli import parse_args
from .cli.auth import handle_auth_login, handle_auth_logout
from .repositories import FavoriteRepository
from .utils import load_settings, setup_logging
from .workers.manager import PipelineConfig

logger = logging.getLogger(__name__)


def main():
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

    try:
        pipeline_config = PipelineConfig(
            num_resolve_workers=args.resolve_workers,
            num_download_workers=args.download_workers,
            num_merge_workers=args.merge_workers,
            resolve_rate_limit=args.resolve_rate_limit,
            download_rate_limit=args.download_rate_limit,
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
    )
    app.run()


if __name__ == "__main__":
    main()
