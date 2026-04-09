# Manga Archiver

A terminal-based manga downloader and archiver.

## About The Project

A terminal-based tool that makes it easy to search for and download manga from sources like MangaDex.

## Features

- Interactive TUI with keyboard and mouse support
- Download chapters in PDF, CBZ, or EPUB format
- Configurable output settings via in-app Settings screen
- Asynchronous download pipeline with configurable workers
- Local file output or Google Drive upload modes
- Backlog sync - automatically find and download missing chapters from your favorites

## Getting Started

### Prerequisites

- Python 3.10 or higher

### Installation

install the package with pip:

```sh
pip install manga-archiver
```

or clone the repository and install the package locally:

```sh
git clone https://github.com/jfang324/manga-archiver.git
cd manga-archiver
pip install .
```

### Running the Application

```sh
manga-archiver
```

## Google Drive Integration

The application supports uploading downloaded manga directly to Google Drive for cloud storage.

### Setting Up Google Drive

1. **Create a Google Cloud Project**
    - Go to [Google Cloud Console](https://console.cloud.google.com/)
    - Create a new project
    - Enable the "Google Drive API"

2. **Create OAuth Credentials**
    - Go to "APIs & Services" > "Credentials"
    - Create "OAuth client ID" credentials
    - Application type: TVs and Limited Input Devices
    - Download the credentials JSON file

3. **Configure the Application**
    - Download your OAuth credentials JSON file from Google Cloud Console
    - Rename it to `client_secret.json` and place it in `~/.manga-archiver/`

    The file should have this structure (from Google's download):

    ```json
    {
        "installed": {
            "client_id": "...",
            "client_secret": "...",
            "redirect_uris": [...],
            "token_uri": "..."
        }
    }
    ```

4. **Authenticate**
    ```sh
    manga-archiver auth login
    ```
    This will initiate the OAuth device flow, follow the instructions in the terminal.

### Using Google Drive

Once authenticated, you can:

- **Use archive mode** to upload downloads directly to Google Drive:

    ```sh
    manga-archiver --archive
    ```

- **Logout** when you want to disconnect your account:
    ```sh
    manga-archiver auth logout
    ```

### How It Works

1. A root folder "Manga-Archiver" is created in your Google Drive
2. Each manga gets its own subfolder (created automatically or reused if existing)
3. Downloaded files are uploaded to the corresponding manga folder
4. File name collisions are handled by appending (1), (2), etc.

### Backlog Sync

The backlog sync feature automatically finds missing chapters from your favorites by comparing your local downloads (stored in Google Drive) against the available chapters.

**Usage:**

```sh
# Sync missing chapters from favorites (requires --archive for Google Drive access)
manga-archiver --archive --backlog
```

This will:

1. Fetch all your favorited manga from the database
2. Scan each manga's folder in Google Drive to see which chapters you have
3. Download any chapters you don't have yet
4. Upload them to Google Drive automatically

**Note:** You must have:

- Authenticated with Google Drive (`manga-archiver auth login`)
- Favorites saved in the app (add manga to favorites in the TUI)
- Run with `--archive` to access Google Drive

### Settings

Press `Ctrl+S` on the Settings screen to save your preferences.

Configurable options:

- **Output Directory**: Where downloaded files are saved (local mode)
- **Output Format**: PDF, CBZ, or EPUB
- **Quality**: 1-100 (higher = better quality, larger files)
- **Optimize**: Optimize PDF file size (slower generation)

Settings are stored in `~/.manga-archiver/settings.json`

## CLI Arguments

The following command-line arguments are available:

| Flag                    | Type | Default | Description                                                        |
| ----------------------- | ---- | ------- | ------------------------------------------------------------------ |
| `--resolve-workers`     | int  | 2       | Number of workers retrieving download resources                    |
| `--download-workers`    | int  | 2       | Number of workers downloading images                               |
| `--merge-workers`       | int  | 2       | Number of workers merging images into output format                |
| `--resolve-rate-limit`  | int  | 5       | Global rate limit for resolve workers (requests/sec)               |
| `--download-rate-limit` | int  | 5       | Global rate limit for download workers (requests/sec)              |
| `--archive`             | flag | false   | Enable archive mode (upload to Google Drive instead of local save) |
| `--backlog`             | flag | false   | Sync favorites with Google Drive and download missing chapters     |
| `--benchmark`           | flag | false   | Enable benchmark metrics collection                                |
| `--auto-exit`           | flag | false   | Automatically exit when all jobs are complete                      |

### Usage Examples

```sh
# Download with more workers for faster processing
manga-archiver --resolve-workers 10 --download-workers 10

# Upload directly to Google Drive
manga-archiver --archive

# Sync missing chapters from favorites
manga-archiver --archive --backlog

# Enable benchmark mode to collect performance metrics
manga-archiver --benchmark
```

For more options, run `manga-archiver --help`.

## Gallery

https://github.com/user-attachments/assets/b4270b0a-4677-48b0-94fc-74b8eb0b0fc9

## Acknowledgements

- [MangaDex](https://mangadex.org/) for providing the API used in this project

## Known Issues

- Currently only supports English translations
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
- ebooklib
- SQLite

### UI

- Textual

### Google Drive

- google-auth
- google-api-python-client

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
