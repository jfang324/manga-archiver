# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2025-04-09

- Move benchmark metrics from logs to `~/.manga-archiver/benchmark/metrics.txt`
- Resolved issue on Windows where the aiodns package would cause SSL errors on API requests

## [1.0.2] - 2025-04-09

- Added `--auto-exit` flag to automatically exit when all jobs are complete

## [1.0.1] - 2025-04-09

- Added CHANGELOG.md
- Minor internal refactor

## [1.0.0] - 2025-04-09

- Initial release supporting CBZ, PDF, EPUB sourced from MangaDex
