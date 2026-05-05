# Development Guide

## Setup

Install dependencies including dev dependencies:

```bash
poetry install --with dev
```

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

## Code Quality

Run linting, type checking, formatting:

```bash
make check
```

## Project Layout

```text
manga-archiver/
├── src/manga_archiver/
│   ├── main.py                 # CLI entry point
│   ├── app.py                  # Textual app root
│   ├── pipeline/               # Pipeline orchestration
│   │   ├── manager.py          # Pipeline manager
│   │   ├── worker_manager.py   # Worker pool orchestration
│   │   ├── job_registry.py     # Job status and retry tracking
│   │   └── benchmark.py        # Pipeline benchmark aggregation
│   ├── backlog_sync.py         # Backlog sync workflow
│   ├── cli/                    # CLI parsing
│   ├── constants/              # Shared constants
│   ├── db/                     # SQLite setup and migrations
│   ├── integrations/           # External providers
│   ├── models/                 # Domain models
│   ├── repositories/           # Persistence access
│   ├── screens/                # Workflow orchestration
│   ├── widgets/                # UI components
│   ├── workers/                # Worker implementations
│   └── utils/                  # Shared utilities
├── tests/unit/                 # Unit tests
├── docs/                       # Documentation
├── pyproject.toml              # Project config
├── Makefile                    # Dev commands
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
- **Benchmark output**: `~/.manga-archiver/benchmark/metrics.txt`
- **Default download path**: `~/Downloads/`
