from argparse import ArgumentParser, _SubParsersAction


def add_auth_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register auth subcommands."""
    auth_parser = subparsers.add_parser("auth", help="Google Drive authentication")
    auth_subparsers = auth_parser.add_subparsers(
        dest="auth_command",
        required=True,
        metavar="{login, logout}",
    )

    auth_subparsers.add_parser("login", help="Log in to Google Drive")
    auth_subparsers.add_parser("logout", help="Log out of Google Drive")

    return auth_parser


def add_migrate_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register migration subcommands."""
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_subparsers = migrate_parser.add_subparsers(
        dest="migrate_system",
        required=True,
        metavar="{database, google-drive}",
    )

    migrate_subparsers.add_parser("database", help="Migrate database schema")
    migrate_subparsers.add_parser("google-drive", help="Migrate Google Drive schema")

    return migrate_parser


def add_list_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register list subcommands."""
    list_parser = subparsers.add_parser("list", help="List available resources")
    list_subparsers = list_parser.add_subparsers(
        dest="list_target",
        required=True,
        metavar="{presets}",
    )

    list_subparsers.add_parser("presets", help="List runtime presets")

    return list_parser


def add_health_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register health subcommand."""
    return subparsers.add_parser(
        "health",
        help="Check content provider API health",
    )


def add_config_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register config subcommands."""
    config_parser = subparsers.add_parser("config", help="Configure integrations")
    config_subparsers = config_parser.add_subparsers(
        dest="config_target",
        required=True,
        metavar="{discord}",
    )

    config_subparsers.add_parser("discord", help="Configure Discord webhook notifications")

    return config_parser
