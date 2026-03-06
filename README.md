## About The Project

A CLI tool that makes it easy to search for and download manga from [MangaDex](https://mangadex.org/)

## Getting Started

### Prerequisites

To use this tool, you will need the following:

- Python 3.9, 3.10, or 3.11
- Poetry (for dependency management)
- A terminal with at least **80 columns x 24 rows**

### Installation

To install the tool, run the following commands in your terminal:

1. Clone the repository:

```sh
git clone https://github.com/jfang324/mangadex-downloader.git
```

2. Navigate to the project directory:

```sh
cd mangadex-downloader
```

3. Install the project using Poetry:

```sh
poetry install
```

4. To run the script, use Poetry:

```sh
poetry run mangadex-downloader
```

Or if you've installed it globally:

```sh
mangadex-downloader
```

## CLI Arguments

The following command-line arguments are available:

| Flag           | Type | Default | Description                                           |
| -------------- | ---- | ------- | ----------------------------------------------------- |
| `--page-size`  | int  | 10      | Number of items to display per page in the UI         |
| `--quality`    | int  | 75      | PDF quality (1-100, where 100 is highest)             |
| `--optimize`   | flag | False   | Optimize PDF file size (trade-off: slower generation) |
| `--data-saver` | flag | False   | Download lower quality images (uses less bandwidth)   |

### Usage Examples

Basic usage with defaults:

```sh
mangadex-downloader
```

High quality PDFs with data-saver mode:

```sh
mangadex-downloader --quality 95 --data-saver
```

Optimized PDFs with more items per page:

```sh
mangadex-downloader --page-size 20 --optimize
```

## Terminal Requirements

**Minimum terminal size: 80 columns x 24 rows**

If your terminal is too small, you'll see this error:

```
============================================================
ERROR: Terminal window too small
============================================================

Minimum required: 80 columns x 24 rows
Current size: [your terminal size]

Please resize your terminal window and try again.
============================================================
```

## Gallery & Demonstrations

https://github.com/user-attachments/assets/90d6f14f-1847-4bd9-9de3-947c70ff6060

## Acknowledgements

- [MangaDex](https://mangadex.org/) for providing the API used in this project

## Known Issues

- Currently only supports english translations
- Characters that can't be used in file names cause unexpected behavior when generating the PDF file when they are included in the title of the manga
- Characters used for query parameters cause unexpected behavior included in user input
- Data-saver mode (`--data-saver` flag) may not work due to issues with MangaDex's CDN; the feature is implemented correctly but the CDN endpoints are currently broken

## Development

To run the tests:

```sh
coverage run -m pytest -v
```

To generate a coverage report:

```sh
coverage report -m
```

To lint the code:

```sh
ruff check .
```

To check types:

```sh
pyright
```

## Contact

Jeffery Fang - [jefferyfang324@gmail.com](mailto:jefferyfang324@gmail.com)

## Tools & Technologies

### Core

- Python 3.9+
- aiohttp (async HTTP client)
- Pillow (image processing)

### CLI

- Curses/Windows-Curses (terminal UI)
- Ruff (linting and formatting)

### Testing

- Pytest
- Coverage
- pytest-asyncio

### Build & Package

- Poetry (dependency management and packaging)
- Pyright (type checking)
