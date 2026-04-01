# MangaDex Downloader

A terminal-based manga reader with a Textual UI.

## About The Project

A terminal-based tool that makes it easy to search for and download manga.

## Features

- Textual-based terminal UI
- Search for manga
- Favorites for quick access to saved manga
- Download chapters in PDF or CBZ format
- Configurable output settings via in-app Settings screen
- Asynchronous download pipeline with configurable workers
- Settings persistence

## Getting Started

### Prerequisites

- Python 3.10 or higher

### Installation

```sh
pip install .
```

## Usage

```sh
mangadex-downloader
```

### Navigation

The application uses a menu-driven interface:

- **Search**: Search for manga
- **Favorites**: View saved favorites
- **Downloads**: View download progress
- **Settings**: Configure output settings

Use arrow keys to navigate, Enter to select, and Escape to go back.

### Settings

Press `Ctrl+S` on the Settings screen to save your preferences.

Configurable options:
- **Output Directory**: Where downloaded files are saved
- **Output Format**: PDF or CBZ (EPUB coming soon)
- **Quality**: 1-100 (higher = better quality, larger files)
- **Optimize**: Optimize PDF file size (slower generation)

Settings are stored in `~/.mangadex-downloader/settings.json`

## CLI Arguments

The following command-line arguments are available:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--resolve-workers` | int | 5 | Number of workers retrieving download resources |
| `--download-workers` | int | 5 | Number of workers downloading images |
| `--merge-workers` | int | 5 | Number of workers merging images into output format |
| `--resolve-rate-limit` | int | 5 | Global rate limit for resolve workers |
| `--download-rate-limit` | int | 5 | Global rate limit for download workers |

### Usage Examples

```sh
mangadex-downloader --resolve-workers 10 --download-workers 10
```

For more options, run `mangadex-downloader --help`.

## Gallery

https://github.com/user-attachments/assets/b4270b0a-4677-48b0-94fc-74b8eb0b0fc9


## Acknowledgements

- [MangaDex](https://mangadex.org/) for providing the API used in this project

## Known Issues

- Currently only supports English translations
- EPUB format is not yet implemented (work in progress)
- Data-saver mode may not work due to issues with MangaDex's CDN

## Development

### Activate Virtual Environment

```sh
poetry shell
```

### Running Tests

```sh
coverage run -m pytest -v
```

### Generating Coverage Report

```sh
coverage report -m
```

### Linting

```sh
ruff check .
```

### Formatting

```sh
ruff format .
```

### Type Checking

```sh
pyright
```

## Tools & Technologies

### Core

- Python 3.10+
- aiohttp
- asyncio
- Pillow
- SQLite

### UI

- Textual

### Code Quality

- Ruff
- Pyright

### Testing

- Pytest
- Coverage
- pytest-asyncio

### Build & Package

- Poetry
- pip
