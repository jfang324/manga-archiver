from argparse import ArgumentParser, _SubParsersAction


def add_auth_parser(subparsers: _SubParsersAction) -> ArgumentParser:
    """Register auth subcommands."""
    auth_parser = subparsers.add_parser("auth", help="Google Drive authentication")
    auth_subparsers = auth_parser.add_subparsers(
        dest="auth_command",
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
        metavar="{database, google-drive}",
    )

    migrate_subparsers.add_parser("database", help="Migrate database schema")
    migrate_subparsers.add_parser("google-drive", help="Migrate Google Drive schema")

    return migrate_parser
