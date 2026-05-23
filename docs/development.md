# Development Guide

## Setup

Install dependencies including dev dependencies:

```bash
poetry install --with dev
```

Install both Git hook stages:

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push
```

The pre-push hook runs heavier local checks like Pyright and pytest before pushing.

## Running the App

Enter the virtual environment:

```bash
poetry shell
```

Then run the application:

```bash
manga-archiver
```

## Testing

Run all tests and generate coverage report:

```bash
make test
make report
```

Run a targeted test file or test case:

```bash
poetry run coverage run -m pytest tests/unit/workers/test_download_worker.py -v
poetry run coverage run -m pytest tests/unit/workers/test_download_worker.py::TestDownloadWorkerDoWork::test_do_work_returns_merging_job -v
```

## Code Quality

Run linting, type checking, formatting:

```bash
make check
```

## Project Layout

```text
manga-archiver/
├── src/manga_archiver/
│   ├── app.py                  # Textual app root
│   ├── backlog_sync.py         # Backlog sync workflow
│   ├── headless_runner.py      # Non-interactive run support
│   ├── health.py               # Health check command support
│   ├── main.py                 # CLI entry point
│   ├── cli/                    # CLI parsing
│   ├── constants/              # Shared constants
│   ├── db/                     # SQLite setup and migrations
│   ├── integrations/           # External providers
│   ├── models/                 # Domain models
│   ├── persistence/            # JSON-backed stores
│   ├── pipeline/               # Pipeline orchestration
│   ├── repositories/           # Persistence access
│   ├── screens/                # Textual screens
│   ├── utils/                  # Shared utilities
│   ├── widgets/                # UI components
│   └── workers/                # Worker implementations
├── tests/unit/                 # Unit tests
├── docs/                       # Documentation
├── CHANGELOG.md                # Release notes
├── LICENSE                     # Project license
├── Makefile                    # Dev commands
├── pyproject.toml              # Project config
└── README.md                   # User guide
```

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        MangaArchiverApp (TUI)                            │
└───────┬──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────┐
│   PipelineManager  │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│      Scheduler     │
└───────┬────────────┘
        │
        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Resolve   │────▶│  Download   │────▶│   Merge     │────▶│   Upload    │
│   Worker    │     │   Worker    │     │   Worker    │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
        │                   │                    │                    │
        ▼                   ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│     utils     │     ContentProviderManager     │    GoogleDriveClient   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

- **Resolve**: Content sources usually expose CDN URLs for images from an API endpoint, we need to retrieve them first
- **Download**: Download images from CDN
- **Merge**: Combine images into PDF/CBZ/EPUB
- **Upload**: Upload to Google Drive (if --archive enabled)

## Logs & Config

- **Logs**: `~/.manga-archiver/logs/`
- **Settings**: `~/.manga-archiver/settings.json`
- **Webhooks**: `~/.manga-archiver/webhooks.json`
- **Resumable jobs**: `~/.manga-archiver/resumable-jobs.json`
- **Benchmark output**: `~/.manga-archiver/benchmark/metrics.txt`
- **Default download path**: `~/Downloads/`
