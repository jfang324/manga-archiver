# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-04-22

- Improved performance of backlog processing when multiple sources are used
- Fixed AllManga integration

## [1.1.4] - 2025-04-22

- Fixed issue where 502 Bad Gateway errors would cause immediate fails instead of correctly retrying
- Improved backlog processing performance by adding per-provider rate limits and round-robin-style scheduling

## [1.1.3] - 2025-04-21

- Fixed issue where manga with long titles or chapter titles would cause upload to fail

## [1.1.2] - 2025-04-21

- Fixed issue where app instantly crashes if no Downloads directory exists
- Fixed issue where `--backlog` would skip valid chapters if the source doesn't have a chapter title
- Fixed issue where `--backlog` would incorrectly skip existing chapters

## [1.1.1] - 2025-04-19

- Improved UI performance on high loads, should be less laggy now
- Added experimental rate limit fix for AllManga

## [1.1.0] - 2025-04-16

- Added support for AllManga (potentially unstable)
- Added infinite scrolling pagination for search results
- Added migration commands to handle database and Google Drive schema updates, required if using a previous version

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
