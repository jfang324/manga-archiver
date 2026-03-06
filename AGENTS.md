# Agents Development Guide

This document provides guidelines and instructions for agents working on the mangadex-downloader project.

## Build, Lint, and Test Commands

### Poetry Workflow
This project uses Poetry for dependency management:
- Install dependencies: `poetry install`
- Install dev dependencies: `poetry install --with dev`
- Run the application: `poetry run mangadex-downloader`
- Run commands in virtual env: `poetry run <command>`

### Running Tests
- Run all tests: `coverage run -m pytest -v`
- Run a single test file: `coverage run -m pytest tests/unit/test_api_access_services.py -v`
- Run a specific test class: `coverage run -m pytest tests/unit/test_api_access_services.py::TestFetch -v`
- Run a specific test method: `coverage run -m pytest tests/unit/test_api_access_services.py::TestFetch::test_fetch_success_returns_json -v`
- Run tests matching a pattern: `coverage run -m pytest -k "test_retrieve" -v`
- Run with detailed output: `coverage run -m pytest -vv`
- Generate coverage report: `coverage report -m`
- Generate HTML coverage report: `coverage html`

### Code Quality Tools
The project uses Ruff for linting and formatting:
- Lint all files: `ruff check .`
- Lint specific file: `ruff check src/mangadex_downloader/main.py`
- Lint with auto-fix: `ruff check --fix .`
- Format code: `ruff format .`

## Project Structure
```
mangadex-downloader/
├── src/mangadex_downloader/
│   ├── __init__.py
│   ├── main.py                    # Entry point, CLI initialization
│   └── services/
│       ├── api_access_service.py  # MangaDex API calls (aiohttp)
│       ├── data_processing_service.py
│       ├── file_access_service.py
│       ├── session_manager.py      # aiohttp.ClientSession management
│       └── user_interface_service.py # Curses UI handling
├── tests/
│   ├── unit/
│   │   ├── test_api_access_services.py
│   │   ├── test_data_processing_service.py
│   │   └── test_file_access_service.py
│   └── mock_data.py                # Shared test fixtures
├── .env                            # Environment variables (not committed)
├── pyproject.toml                  # Poetry configuration
└── README.md
```

## Code Style Guidelines

### Imports
- Use absolute imports from `src.mangadex_downloader` package
- Service modules use `from module import *` pattern (as in main.py)
- Order: standard library → third-party → local imports
- All imports on separate lines, never grouped

### Naming Conventions
- Variables/functions: snake_case (`user_input`, `manga_data`)
- Classes: PascalCase (`SessionManager`, `UserInterface`)
- Constants: UPPER_CASE (`MAX_RETRIES`, `DEFAULT_LIMIT`)
- Modules: snake_case (`api_access_service.py`)
- Private methods/attributes: leading underscore (`_private_method`, `_cache`)

### Types and Annotations
- All functions MUST have type annotations (no exceptions)
- Use specific types instead of generic `Any`
- Collection types: `list[str]`, `dict[str, int]`, `set[str]`
- Optional parameters: use `None` explicitly, e.g., `param: str | None = None`
- Return types required for all functions

### Formatting
- Indentation: 4 spaces (no tabs)
- Line length: Recommended under 100 characters
- Use parentheses for line continuation

### Docstrings
All functions must include docstrings using this format:
```python
"""
Short description of function purpose.

:param param_name: Description of parameter
:return: Description of return value
"""
```

- Handle exceptions with try/except blocks
- For expected failures: catch exception, print error, return `None`
- For unexpected failures: consider raising with meaningful message
- Async functions should handle exceptions internally unless re-raising is intentional
- Log errors with print statements (current project pattern)

### Async/Await Patterns
- All I/O operations use async/await
- Use `asyncio.gather()` for concurrent operations
- Always pass session objects to async functions
- Never block the event loop with synchronous operations

## Code Structure

### Service Architecture
- All services in `src/mangadex_downloader/services/`
- Each service should have a single, focused responsibility
- Services communicate via function calls, not shared state
- Use dependency injection (pass sessions, managers as parameters)

### Session Management
- Always use the SessionManager for aiohttp.ClientSession
- Sessions should be created once and reused
- Close sessions when done to release resources

## Testing Patterns
- Tests in `tests/unit/` mirror the services structure
- Test classes named after the module/function being tested
- Test methods: `test_<operation>_<expected_result>`
- Use `unittest.mock.AsyncMock` for async functions, `MagicMock` for context managers
- Use `@patch` decorator for mocking module-level functions
- Async test methods use pytest-asyncio (`asyncio_mode = "auto"`)

## Special Considerations

### Curses CLI Application
- This is a curses-based terminal UI application
- On Windows, use `windows-curses` package
- Always restore terminal state on exit (use try/finally)
- Screen dimensions may vary - use dynamic sizing

### API Integration
- Uses MangaDex API (https://api.mangadex.org)
- Endpoints: `/manga`, `/manga/{id}/feed`, `/at-home/server/{id}`
- Requires environment variables for API URLs

### Known Issues
- Only supports English translations
- Special characters in manga titles may cause PDF generation issues
- Query parameters in user input may cause unexpected behavior
- No rate limiting - be respectful of API

## Environment Requirements
Base URLs are defined in `src/mangadex_downloader/constants.py`.

Dependencies: Python 3.9+, aiohttp (speedups), Pillow, windows-curses (Windows), pytest/pytest-asyncio/coverage (dev)

## Development Workflow
1. Run existing tests to establish baseline
2. Make changes following code style guidelines
3. Run relevant tests, ensure all pass
4. Run `ruff check .` and `ruff format .`
5. Run `coverage report -m` to ensure no regressions
