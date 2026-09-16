from argparse import Namespace
from dataclasses import dataclass

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


@dataclass(frozen=True)
class SubcommandResult:
    """Result returned by a CLI subcommand handler."""

    handled: bool = False
    exit_code: int | None = None


async def handle_workflow_subcommands(
    args: Namespace,
    webhook_config_store: WebhookConfigStore,
) -> SubcommandResult:
    """Handle CLI subcommands that run separate workflows and exit.

    Returns:
        SubcommandResult: The command handling status and exit code.
    """
    result = _handle_list(args)
    if result.handled:
        return result

    result = await _handle_auth(args)
    if result.handled:
        return result

    result = await _handle_health(args)
    if result.handled:
        return result

    result = await _handle_config(args, webhook_config_store)
    if result.handled:
        return result

    result = await _handle_migrations(args)
    if result.handled:
        return result

    return SubcommandResult()


def _handle_list(args: Namespace) -> SubcommandResult:
    """Handle list subcommands."""
    if args.command != "list":
        return SubcommandResult(handled=False, exit_code=EXIT_SUCCESS)

    if args.list_target == "presets":
        print(format_presets())
        return SubcommandResult(handled=True, exit_code=EXIT_SUCCESS)

    return SubcommandResult(handled=True, exit_code=EXIT_INIT_ERROR)


async def _handle_auth(args: Namespace) -> SubcommandResult:
    """Handle authentication commands."""
    if args.command != "auth":
        return SubcommandResult(handled=False, exit_code=EXIT_SUCCESS)

    if args.auth_provider != "google-drive":
        print(f'Unsupported auth provider: {args.auth_provider}. Only "google-drive" is supported.')
        return SubcommandResult(handled=True, exit_code=EXIT_AUTH_ERROR)

    if args.auth_action == "login":
        result = await handle_auth_login()
        return SubcommandResult(handled=True, exit_code=result)

    if args.auth_action == "logout":
        result = await handle_auth_logout()
        return SubcommandResult(handled=True, exit_code=result)

    return SubcommandResult(handled=True, exit_code=EXIT_AUTH_ERROR)


async def _handle_config(
    args: Namespace,
    webhook_config_store: WebhookConfigStore,
) -> SubcommandResult:
    """Handle configuration commands."""
    if args.command != "config":
        return SubcommandResult(handled=False, exit_code=EXIT_SUCCESS)

    if args.config_category != "webhooks":
        print(f'Unsupported config category: {args.config_category}. Only "webhooks" is supported.')
        return SubcommandResult(handled=True, exit_code=EXIT_INIT_ERROR)

    try:
        source = WebhookProvider(args.config_target)
    except ValueError:
        return SubcommandResult(handled=True, exit_code=EXIT_INIT_ERROR)

    config = _prompt_webhook_config(source)
    if not config["enabled"]:
        existing_config = (await webhook_config_store.load()).get(source, {})
        config["webhook_url"] = existing_config.get("webhook_url", "")

    try:
        await webhook_config_store.save_config(source, config)
    except ValueError as e:
        print(f"Failed to save {source.value.title()} webhook config: {e}")
        return SubcommandResult(handled=True, exit_code=EXIT_INIT_ERROR)

    print(f"{source.value.title()} webhook config saved.")
    return SubcommandResult(handled=True, exit_code=EXIT_SUCCESS)


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


async def _handle_health(args: Namespace) -> SubcommandResult:
    """Handle provider health command."""
    if args.command != "health":
        return SubcommandResult(handled=False, exit_code=EXIT_SUCCESS)

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
        return SubcommandResult(handled=True, exit_code=EXIT_SUCCESS)

    return SubcommandResult(handled=True, exit_code=EXIT_GENERAL_ERROR)


async def _handle_migrations(args: Namespace) -> SubcommandResult:
    """Handle migration commands."""
    if args.command != "migrate":
        return SubcommandResult(handled=False, exit_code=EXIT_SUCCESS)

    try:
        if args.migrate_system == "database":
            system = "database"

        elif args.migrate_system == "google-drive":
            system = "google_drive"

        else:
            return SubcommandResult(handled=True, exit_code=EXIT_MIGRATION_ERROR)

        print("Running migrations...")
        # SchemaManager opens and initializes the SQLite database, so keep it lazy for
        # migration workflows instead of touching the database for every subcommand.
        schema_manager = SchemaManager()
        result = await schema_manager.run_migrations(system)
        print(f"  {result}")

        return SubcommandResult(handled=True, exit_code=EXIT_SUCCESS)
    except Exception as e:
        print(f"Migration failed: {e}")
        return SubcommandResult(handled=True, exit_code=EXIT_MIGRATION_ERROR)
