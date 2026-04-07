# MangaDex Downloader

A terminal-based manga downloader and archiver.

## About The Project

A terminal-based tool that makes it easy to search for and download manga from MangaDex.

## Features

- Interactive TUI with keyboard and mouse support
- Download chapters in PDF, CBZ, or EPUB format
- Configurable output settings via in-app Settings screen
- Asynchronous download pipeline with configurable workers
- Local file output or Google Drive upload modes

## Getting Started

### Prerequisites

- Python 3.10 or higher

### Installation

```sh
pip install .
```

### Running the Application

```sh
mangadex-downloader
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
    - Application type: Desktop app
    - Download the credentials JSON file

3. **Configure the Application**
   - Download your OAuth credentials JSON file from Google Cloud Console
   - Rename it to `client_secret.json` and place it in `~/.mangadex-downloader/`

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
    mangadex-downloader auth login
    ```
    This will initiate the OAuth device flow, follow the instructions in the terminal.

### Using Google Drive

Once authenticated, you can:

- **Use archive mode** to upload downloads directly to Google Drive:

    ```sh
    mangadex-downloader --archive
    ```

- **Logout** when you want to disconnect your account:
    ```sh
    mangadex-downloader auth logout
    ```

### How It Works

1. A root folder "MangaDex-Downloader" is created in your Google Drive
2. Each manga gets its own subfolder (created automatically or reused if existing)
3. Downloaded files are uploaded to the corresponding manga folder
4. File name collisions are handled by appending (1), (2), etc.

### Settings

Press `Ctrl+S` on the Settings screen to save your preferences.

Configurable options:

- **Output Directory**: Where downloaded files are saved (local mode)
- **Output Format**: PDF, CBZ, or EPUB
- **Quality**: 1-100 (higher = better quality, larger files)
- **Optimize**: Optimize PDF file size (slower generation)

Settings are stored in `~/.mangadex-downloader/settings.json`

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
| `--benchmark`           | flag | false   | Enable benchmark metrics collection                                |

### Usage Examples

```sh
# Download with more workers for faster processing
mangadex-downloader --resolve-workers 10 --download-workers 10

# Upload directly to Google Drive
mangadex-downloader --archive

# Enable benchmark mode to collect performance metrics
mangadex-downloader --benchmark
```

For more options, run `mangadex-downloader --help`.

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
