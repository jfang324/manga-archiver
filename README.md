## About The Project

A CLI tool that makes it easy to search for and download manga from [MangaDex](https://mangadex.org/)

## Getting Started

### Prerequisites

To use this tool, you will need the following:

-   Python 3.9, 3.10, or 3.11
-   aiohttp
-   Pillow
-   windows-curses (if you are using Windows)

To run the tests, you will need the following:

-   Pytest
-   Coverage
-   pytest-asyncio

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

3. If using Windows, install the windows-curses package:

```sh
pip install windows-curses
```

4. Install the project using pip:

```sh
pip install .
```

5. The script will now be installed in your python scripts directory (probably `C:\Users\<username>\AppData\Roaming\Python\Python3.X\Scripts` for Windows users). To run the script, navigate to the scripts directory and run the following command:

```sh
mangadex-downloader
```

6. If you want to be able to run the script from anywhere, you can add the scripts directory to your PATH environment variable.

7. To run the tests, install the development dependencies:

```sh
pip install -r requirements-dev.txt
```

9. Run the tests:

```sh
coverage run -m pytest -v
```

10. Generate a coverage report:

```sh
coverage report -m
```

## Gallery & Demonstrations

https://github.com/user-attachments/assets/90d6f14f-1847-4bd9-9de3-947c70ff6060

## Acknowledgements

-   [MangaDex](https://mangadex.org/) for providing the API used in this project

## Known Issues

- Currently only supports english translations
- Characters that can't be used in file names cause unexpected behavior when generating the PDF file when they are included in the title of the manga
- Characters used for query parameters cause unexpected behavior included in user input
- Data-saver mode (`--data-saver` flag) may not work due to issues with MangaDex's CDN; the feature is implemented correctly but the CDN endpoints are currently broken

## Contact

Jeffery Fang - [jefferyfang324@gmail.com](mailto:jefferyfang324@gmail.com)

## Tools & Technologies

-   Python
-   Curses/Windows-Curses
-   aiohttp
-   Pillow
-   Pytest
-   Coverage
-   Poetry
-   tempfile
