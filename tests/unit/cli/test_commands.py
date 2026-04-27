import pytest

from src.manga_archiver.cli.commands import parse_args
from src.manga_archiver.constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_PROVIDER_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
)

ARGPARSE_USAGE_ERROR = 2


class TestParseArgs:
    def test_defaults_to_application_command_options(self) -> None:
        args = parse_args([])

        assert args.command is None
        assert args.resolve_workers == DEFAULT_RESOLVE_WORKERS
        assert args.download_workers == DEFAULT_DOWNLOAD_WORKERS
        assert args.merge_workers == DEFAULT_MERGE_WORKERS
        assert args.resolve_rate_limit == DEFAULT_PROVIDER_RATE_LIMIT
        assert args.download_rate_limit == DEFAULT_DOWNLOAD_RATE_LIMIT
        assert args.archive is False
        assert args.benchmark is False
        assert args.backlog is False
        assert args.auto_exit is False

    def test_parses_application_command_options(self) -> None:
        args = parse_args(
            [
                "--resolve-workers",
                "3",
                "--download-workers",
                "4",
                "--merge-workers",
                "5",
                "--resolve-rate-limit",
                "6",
                "--download-rate-limit",
                "7",
                "--archive",
                "--benchmark",
                "--backlog",
                "--auto-exit",
            ]
        )

        assert args.resolve_workers == 3
        assert args.download_workers == 4
        assert args.merge_workers == 5
        assert args.resolve_rate_limit == 6
        assert args.download_rate_limit == 7
        assert args.archive is True
        assert args.benchmark is True
        assert args.backlog is True
        assert args.auto_exit is True

    @pytest.mark.parametrize("auth_command", ["login", "logout"], ids=["login", "logout"])
    def test_parses_auth_subcommands(self, auth_command: str) -> None:
        args = parse_args(["auth", auth_command])

        assert args.command == "auth"
        assert args.auth_command == auth_command

    @pytest.mark.parametrize(
        "migrate_system",
        ["database", "google-drive"],
        ids=["database", "google-drive"],
    )
    def test_parses_migrate_subcommands(self, migrate_system: str) -> None:
        args = parse_args(["migrate", migrate_system])

        assert args.command == "migrate"
        assert args.migrate_system == migrate_system

    @pytest.mark.parametrize(
        ("argv", "expected_command", "expected_subcommand_name", "expected_subcommand"),
        [
            (["--archive", "auth", "login"], "auth", "auth_command", "login"),
            (["--archive", "migrate", "database"], "migrate", "migrate_system", "database"),
        ],
        ids=["archive-auth-login", "archive-migrate-database"],
    )
    def test_parses_global_flags_with_subcommands(
        self,
        argv: list[str],
        expected_command: str,
        expected_subcommand_name: str,
        expected_subcommand: str,
    ) -> None:
        args = parse_args(argv)

        assert args.archive is True
        assert args.command == expected_command
        assert getattr(args, expected_subcommand_name) == expected_subcommand

    @pytest.mark.parametrize(
        "argv",
        [["auth"], ["migrate"]],
        ids=["missing-auth-subcommand", "missing-migrate-subcommand"],
    )
    def test_requires_nested_subcommands(self, argv: list[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args(argv)

        assert exc_info.value.code == ARGPARSE_USAGE_ERROR

    def test_rejects_unknown_command(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["unknowncmd"])

        assert exc_info.value.code == ARGPARSE_USAGE_ERROR

    @pytest.mark.parametrize(
        "argv",
        [
            ["--resolve-workers", "0"],
            ["--download-workers", "-1"],
            ["--merge-workers", "abc"],
            ["--resolve-rate-limit", "0"],
            ["--download-rate-limit", "0"],
        ],
        ids=[
            "zero-resolve-workers",
            "negative-download-workers",
            "non-integer-merge-workers",
            "zero-resolve-rate-limit",
            "zero-download-rate-limit",
        ],
    )
    def test_rejects_invalid_positive_int_options(self, argv: list[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args(argv)

        assert exc_info.value.code == ARGPARSE_USAGE_ERROR
