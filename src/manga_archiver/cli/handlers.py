from argparse import Namespace

import aiohttp

from ..constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_GENERAL_ERROR,
    EXIT_INIT_ERROR,
    EXIT_MIGRATION_ERROR,
    EXIT_SUCCESS,
)
from ..db.schema_manager import SchemaManager
from ..health import ProviderHealthChecker, format_provider_health_check_result
from ..integrations.webhooks import WebhookProvider
from ..persistence.webhook_config_store import WebhookConfig, WebhookConfigStore
from ..utils.auth.google_drive import handle_auth_login, handle_auth_logout
from .presets import format_presets


async def handle_workflow_subcommands(
    args: Namespace,
    webhook_config_store: WebhookConfigStore,
) -> int | None:
    """Handle CLI subcommands that run separate workflows and exit.

    Returns:
        int | None: An exit code if the command was handled, None if not
    """
    handled, exit_code = _handle_list(args)
    if handled:
        return exit_code

    handled, exit_code = _handle_auth(args)
    if handled:
        return exit_code

    handled, exit_code = await _handle_health(args)
    if handled:
        return exit_code

    handled, exit_code = await _handle_config(args, webhook_config_store)
    if handled:
        return exit_code

    handled, exit_code = await _handle_migrations(args)
    if handled:
        return exit_code

    return None


def _handle_list(args: Namespace) -> tuple[bool, int]:
    """Handle list subcommands.

    Returns:
        tuple[bool, int]: Tuple of (handled, exit_code). If handled is False, caller should continue.
    """
    if args.command != "list":
        return False, EXIT_SUCCESS

    if args.list_target == "presets":
        print(format_presets())
        return True, EXIT_SUCCESS

    return True, EXIT_INIT_ERROR


def _handle_auth(args: Namespace) -> tuple[bool, int]:
    """Handle authentication commands.

    Returns:
        tuple[bool, int]: Tuple of (handled, exit_code). If handled is False, caller should continue.
    """
    if args.command != "auth":
        return False, EXIT_SUCCESS

    if args.auth_provider != "google-drive":
        print(f'Unsupported auth provider: {args.auth_provider}. Only "google-drive" is supported.')
        return True, EXIT_AUTH_ERROR

    if args.auth_action == "login":
        return True, handle_auth_login()

    if args.auth_action == "logout":
        return True, handle_auth_logout()

    return True, EXIT_AUTH_ERROR


async def _handle_config(
    args: Namespace,
    webhook_config_store: WebhookConfigStore,
) -> tuple[bool, int]:
    """Handle configuration commands."""
    if args.command != "config":
        return False, EXIT_SUCCESS

    if args.config_category != "webhooks":
        print(f'Unsupported config category: {args.config_category}. Only "webhooks" is supported.')
        return True, EXIT_INIT_ERROR

    try:
        source = WebhookProvider(args.config_target)
    except ValueError:
        return True, EXIT_INIT_ERROR

    config = _prompt_webhook_config(source)
    if not config["enabled"]:
        existing_config = (await webhook_config_store.load()).get(source, {})
        config["webhook_url"] = existing_config.get("webhook_url", "")

    try:
        await webhook_config_store.save_config(source, config)
    except ValueError as e:
        print(f"Failed to save {source.value.title()} webhook config: {e}")
        return True, EXIT_INIT_ERROR

    print(f"{source.value.title()} webhook config saved.")
    return True, EXIT_SUCCESS


def _prompt_webhook_config(source: WebhookProvider) -> WebhookConfig:
    """Prompt for webhook configuration for a provider."""
    label = source.value.title()

    enabled_response = ""
    while enabled_response not in {"y", "yes", "n", "no"}:
        enabled_response = input(f"Enable {label} webhook notifications? [y/n]: ").strip().lower()

    enabled = enabled_response in {"y", "yes"}
    webhook_url = ""
    if enabled:
        webhook_url = input(f"{label} webhook URL: ").strip()

    return WebhookConfig(
        enabled=enabled,
        webhook_url=webhook_url,
    )


async def _handle_health(args: Namespace) -> tuple[bool, int]:
    """Handle provider health command."""
    if args.command != "health":
        return False, EXIT_SUCCESS

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    ) as session:
        results = []
        first_result = True
        async for result in ProviderHealthChecker(session).check_all_completed():
            if not first_result:
                print()

            print(format_provider_health_check_result(result))
            results.append(result)
            first_result = False

    if all(result.is_healthy for result in results):
        return True, EXIT_SUCCESS

    return True, EXIT_GENERAL_ERROR


async def _handle_migrations(args: Namespace) -> tuple[bool, int]:
    """Handle migration commands.

    Returns:
        tuple[bool, int]: Tuple of (handled, exit_code). If handled is False, caller should continue.
    """
    if args.command != "migrate":
        return False, EXIT_SUCCESS

    try:
        if args.migrate_system == "database":
            system = "database"

        elif args.migrate_system == "google-drive":
            system = "google_drive"

        else:
            return True, EXIT_MIGRATION_ERROR

        print("Running migrations...")
        # SchemaManager opens and initializes the SQLite database, so keep it lazy for
        # migration workflows instead of touching the database for every subcommand.
        schema_manager = SchemaManager()
        result = await schema_manager.run_migrations(system)
        print(f"  {result}")

        return True, EXIT_SUCCESS
    except Exception as e:
        print(f"Migration failed: {e}")
        return True, EXIT_MIGRATION_ERROR
