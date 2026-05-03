from argparse import Namespace

from ..constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_INIT_ERROR,
    EXIT_MIGRATION_ERROR,
    EXIT_SUCCESS,
)
from ..db.schema_manager import SchemaManager
from ..utils.auth.google_drive import handle_auth_login, handle_auth_logout
from .presets import format_presets


async def handle_subcommands(
    args: Namespace, schema_manager: SchemaManager | None = None
) -> int | None:
    """Handle CLI subcommands before normal app startup.

    Returns:
        int | None: An exit code if the command was handled, None if not
    """
    handled, exit_code = _handle_list(args)
    if handled:
        return exit_code

    handled, exit_code = _handle_auth(args)
    if handled:
        return exit_code

    if schema_manager is None:
        return None

    handled, exit_code = await _handle_migrations(args, schema_manager)
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

    if args.auth_command == "login":
        return True, handle_auth_login()

    if args.auth_command == "logout":
        return True, handle_auth_logout()

    return True, EXIT_AUTH_ERROR


async def _handle_migrations(args: Namespace, schema_manager: SchemaManager) -> tuple[bool, int]:
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

        result = await schema_manager.run_migrations(system)
        print(f"  {result}")

        return True, EXIT_SUCCESS
    except Exception as e:
        print(f"Migration failed: {e}")
        return True, EXIT_MIGRATION_ERROR
