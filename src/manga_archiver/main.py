import asyncio
import logging
import sys

from .bootstrap import (
    build_app,
    build_async_dependencies,
    build_configurations,
    build_persistence_stores,
    create_client_session,
    initialize_google_drive,
    load_backlog,
    validate_schema_versions,
)
from .cli import parse_args
from .cli.handlers import handle_workflow_subcommands
from .constants.exit_codes import (
    EXIT_GENERAL_ERROR,
    EXIT_INIT_ERROR,
    EXIT_RUNTIME_ERROR,
)
from .db.schema_manager import SchemaManager
from .headless_runner import HeadlessPipelineRunner
from .pipeline import PipelineManager
from .repositories import FavoriteRepository
from .utils import setup_logging
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entry point - creates an event loop and runs the application."""
    asyncio.run(_async_main())


async def _async_main() -> None:
    """Set up dependencies and run the application."""
    args = parse_args()
    (
        resumable_jobs_store,
        settings_store,
        webhook_config_store,
        google_drive_token_store,
    ) = build_persistence_stores()

    setup_logging()

    subcommand_result = await handle_workflow_subcommands(
        args,
        webhook_config_store,
    )
    if subcommand_result.handled:
        sys.exit(subcommand_result.exit_code)

    schema_manager = SchemaManager()

    google_drive_enabled = args.archive
    validation_result = validate_schema_versions(schema_manager, google_drive_enabled)
    if validation_result.message is not None:
        print(validation_result.message)

    if validation_result.exit_code is not None:
        sys.exit(validation_result.exit_code)

    google_drive_archive_store = None
    google_drive_folder_cache = None
    google_drive_token = None

    if google_drive_enabled:
        init_result = await initialize_google_drive(schema_manager, google_drive_token_store)
        if init_result.message is not None:
            print(init_result.message)

        if init_result.exit_code is not None:
            sys.exit(init_result.exit_code)

        google_drive_archive_store = init_result.archive_store
        google_drive_folder_cache = init_result.folder_cache
        google_drive_token = init_result.token

    try:
        pipeline_config, app_config = await build_configurations(args, settings_store)
        favorite_repository = FavoriteRepository()
        client_session = create_client_session()
    except Exception as e:
        logger.error("Failed to initialize: %s", e)
        sys.exit(EXIT_INIT_ERROR)

    async with client_session as session:
        try:
            (
                provider_manager,
                download_client,
                webhook_client,
            ) = await build_async_dependencies(session, args, webhook_config_store)
            backlog_result = await load_backlog(
                args=args,
                favorite_repository=favorite_repository,
                google_drive_archive_store=google_drive_archive_store,
                provider_manager=provider_manager,
                app_config=app_config,
            )

            if backlog_result.message is not None:
                print(backlog_result.message)

            if backlog_result.exit_code is not None:
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
                exit_code = await HeadlessPipelineRunner(
                    pipeline_manager=pipeline_manager,
                    webhook_client=webhook_client,
                ).run(backlog)
                sys.exit(exit_code)

            resumable_jobs = await resumable_jobs_store.get_resumable_jobs()
            await resumable_jobs_store.clear_resumable_jobs()

            app = build_app(
                app_config=app_config,
                pipeline_manager=pipeline_manager,
                favorite_repository=favorite_repository,
                provider_manager=provider_manager,
                settings_store=settings_store,
                backlog=backlog,
                resumable_jobs=resumable_jobs,
            )
        except Exception as e:
            logger.error("Failed to initialize: %s", e)
            sys.exit(EXIT_INIT_ERROR)

        try:
            incomplete_jobs = await app.run_async()
        except Exception as e:
            logger.error("Runtime error during app execution: %s", e)
            sys.exit(EXIT_RUNTIME_ERROR)

        try:
            if not isinstance(incomplete_jobs, list):
                raise ValueError("Incomplete jobs must be a list")

            if not all(
                isinstance(incomplete_job, FetchingResourcesJob)
                for incomplete_job in incomplete_jobs
            ):
                raise ValueError("Incomplete jobs must contain only FetchingResourcesJob instances")

            await resumable_jobs_store.save_resumable_jobs(incomplete_jobs)
        except Exception as e:
            logger.error("Failed to save incomplete jobs: %s", e)
            sys.exit(EXIT_GENERAL_ERROR)


if __name__ == "__main__":
    main()
