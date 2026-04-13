# Agents Development Guide

This document provides guidelines and instructions for agents working on the manga-archiver project.

## Build, Lint, and Test Commands

### Poetry Workflow
This project uses Poetry for dependency management:
- Install dependencies: `poetry install`
- Install dev dependencies: `poetry install --with dev`
- Run the application: `poetry run manga-archiver`
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

#### Ruff (Linting & Formatting)
The project uses Ruff for linting and formatting:
- Lint all files: `ruff check .`
- Lint specific file: `ruff check src/manga_archiver/main.py`
- Lint with auto-fix: `ruff check --fix .`
- Format code: `ruff format .`

**Ruff Configuration** (from pyproject.toml):
- Enabled rules: E, F, W, I, N, UP, B, A, C4, T20, S, PERF, FIX, ARG
- Ignored rules: E501, B008, PTH110, PTH112, PTH113, PTH118, PTH119, PTH208, PTH109, B904, T201
- Line length: 100 characters
- Docstring convention: Google
- Max function complexity: 10

#### Pyright (Type Checking)
- Run type checking: `poetry run pyright`
- Type checking mode: basic
- Python version: 3.9+

## Project Structure
```
manga-archiver/
├── src/manga_archiver/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── app.py                  # Main Textual application
│   ├── constants.py            # API URLs
│   │   └── menu_options.py    # Menu option definitions
│   ├── workers/                # Async worker pipeline
│   │   ├── base.py           # Base worker class
│   │   ├── manager.py        # Pipeline manager
│   │   ├── resolve_worker.py # MangaDex API worker
│   │   ├── download_worker.py # Image download worker
│   │   ├── merge_worker.py   # PDF/CBZ generation worker
│   │   ├── benchmark_worker.py # Timing tracker
│   │   └── jobs.py           # Job dataclasses
│   ├── screens/                # Textual screens
│   │   ├── menu_screen.py
│   │   ├── search_screen.py
│   │   └── selection_screen.py
│   ├── widgets/                # Custom Textual widgets
│   │   ├── menu_selector.py
│   │   ├── search_panel.py
│   │   └── selection_panel.py
│   ├── utils/                  # Utilities
│   │   ├── downloader.py      # Image download client
│   │   ├── multi_format_exporter.py # PDF/CBZ generation
│   │   ├── session_manager.py # aiohttp.ClientSession
│   │   └── logger.py         # Logging setup
│   ├── models/                 # Data models
│   │   └── app_config.py
│   └── integrations/           # API clients
│       ├── base.py            # Provider interface
│       ├── exceptions.py      # Custom exceptions
│       └── mangadex/         # MangaDex API
│           └── client.py
├── tests/
│   └── unit/
│       ├── workers/           # Worker unit tests
│       ├── widgets/           # Widget unit tests
│       ├── utils/             # Utility tests
│       └── integrations/      # API client tests
├── pyproject.toml
└── README.md
```

## Code Style Guidelines

### Imports
- Use absolute imports from `src.mangadex_downloader` package
- Service modules use `from module import *` pattern (as in main.py)
- Order: standard library → third-party → local imports
- All imports on separate lines, never grouped

### Import Patterns and Type Hints

**Top-level imports are mandatory:**
```python
# ✅ GOOD - clear, explicit dependencies
from aiohttp import ClientSession
from .mangadex.client import MangaDexApiClient

class ContentProviderManager:
    def __init__(self, session: ClientSession):
        self._providers = {
            ContentSource.MANGADEX: MangaDexApiClient(session),
        }
```

**In-function imports are prohibited except for documented reasons:**
```python
# ❌ BAD - hides dependencies, poor testability
class ContentProviderManager:
    def __init__(self, session):
        from .mangadex.client import MangaDexApiClient  # Anti-pattern

# ✅ Only acceptable: documented architectural reason
# from .expensive_module import HeavyDependency  # Startup optimization
```

#### TYPE_CHECKING Guidelines

Use `TYPE_CHECKING` only when testing proves circular imports cannot be resolved:

```python
# ✅ GOOD - Prevents documented circular import A→B→A
if TYPE_CHECKING:
    from .module_b import SomeClass

# ❌ BAD - Symbol imported at module level anyway
from aiohttp import ClientSession

if TYPE_CHECKING:
    from aiohttp import ClientSession  # Redundant
```

#### __future__.annotations Guidelines

Use `from __future__ import annotations` only when forward references exist:

```python
# ✅ GOOD - Forward reference to class defined later
class A:
    def method(self) -> "B":  # Forward reference - needs __future__
        pass

class B:
    pass

# ❌ BAD - No forward references, unnecessary complexity
class ContentProviderManager:
    def __init__(self, session: ClientSession):  # No forward reference needed
        pass
```

**Verification steps before committing:**
1. Run `python -c "import your_module"` - No ImportError
2. Run `ruff check .` - Passes linting
3. Run test suite - All tests pass

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
- Quote style: double quotes (per ruff format config)

### Docstrings

Use Google-style docstrings, but be pragmatic:
- Document public APIs, complex logic, non-obvious behavior
- Skip docstrings on test methods (test name is sufficient)
- Skip docstrings on obvious functions (name explains itself)
- 1-liner for simple things (exceptions, basic dataclasses)
- Target: 15-20% comment ratio for this project size
```python
"""
Short description of function purpose.

Args:
    param_name: Description of parameter

Returns:
    Description of return value
"""
```

### Logging Patterns

**Module-level logger:**
- Always use module-level logger: `logger = logging.getLogger(__name__)`
- Never use root logger (`logging.error(...)`) — it loses module context
- Use `%s` formatting, not f-strings: `logger.error("Context: %s", e)`

```python
import logging

logger = logging.getLogger(__name__)

# Good
logger.error("Failed to process: %s", e)

# Bad
logging.error(f"Failed to process: {e}")  # Loses module name
logger.error(f"Failed to process: {e}")   # Extra string interpolation
```

### Error Handling

**For API/Service Clients:**
- Log with module-level logger for debugging
- Use bare `raise` (not `raise e`) to preserve traceback
- Raise exceptions to let consumers handle them

```python
try:
    response = await self._request(url, params)
except (NotFoundError, RateLimitError, ApiError) as e:
    logger.error("Error searching manga: %s", e)
    raise  # Bare raise preserves traceback
```

**For Screen/UI Consumers:**
- Catch exceptions, show user-friendly notifications
- Don't log if the module already logs (avoids duplicate entries)
- Distinguish RateLimitError with specific message

```python
try:
    results = await self._client.search_manga(query)
except RateLimitError:
    self.notify("Too many requests. Please wait a moment.", severity="error")
except (NotFoundError, ApiError):
    self.notify("Error searching for manga", severity="error")
```

- Never expose raw exception details in `notify()` messages
- Use specific exception types when catching
- Don't duplicate logs — let modules handle logging

## Code Quality Standards

Target quality level for new code:
- Code Quality: 8/10
- Maintainability: 8/10
- Best Practices: 8/10

This means:
- Build UI in `compose()`, not in `on_mount()`
- Use reactive properties and built-in widget APIs (e.g., `ListView.index` instead of manual iteration)
- Modern type hints: use `int | None` instead of `Union[int, None]`
- Minimal, focused methods with single responsibility
- Proper message-based communication (widgets emit messages, parent handles actions)
- No redundant validation (e.g., don't manually check if `query_one()` found widgets - it throws `NoMatches`)

## Async/Await Patterns
- All I/O operations use async/await
- Use `asyncio.gather()` for concurrent operations
- Always pass session objects to async functions
- Never block the event loop with synchronous operations

## Service Architecture
- All services in `src/mangadex_downloader/` (grouped by function)
- Workers in `workers/` - each worker has single responsibility
- Workers communicate via asyncio Queues
- Use dependency injection (pass sessions, managers as parameters)

## Session Management
- Always use the SessionManager for aiohttp.ClientSession
- Sessions should be created once and reused
- Close sessions when done to release resources

## Testing Patterns

### Core Principles

**Test behavior, not infrastructure.** Focus on what the code *does* (callback invoked
with correct data, file written with correct content) rather than *how* it does it
(queue processing, thread management).

**No fake tests.** A test that doesn't actually run the code being tested is worthless:
- Manually invoking a callback instead of letting the worker invoke it
- Creating a worker but never calling `run()` or `_do_work()`
- Mocking queue.get() to return a value, then manually calling the callback instead
  of letting the worker call it

**No half-baked assertions.** Verify actual values, not just types or existence:
- Good: `assert config.quality == 75` or `mock_callback.assert_called_once_with(...)`
- Bad: `assert isinstance(config, AppConfig)` (only checks type, not values)

**No pointless tests.** Don't test framework behavior:
- Don't test dataclass default values (Python handles this)
- Don't test exception inheritance
- Don't test that `pytest.raises` works

### Testing Workers with Callbacks

For workers that invoke callbacks (like NotificationWorker):

```python
# Mock queue to return a known job
mock_queue = MagicMock()
mock_queue.get = AsyncMock(return_value=NotificationJob(
    id="job_123",
    manga_title="Test Manga",
    ...
))

# Create worker and run
worker = NotificationWorker(..., input_queue=mock_queue, on_status_callback=mock_callback)
await worker._do_work(await mock_queue.get())

# Verify callback was invoked with correct extracted data
mock_callback.assert_called_once_with("job_123", JobStatus.COMPLETED, expected_metadata)
```

This tests that job data flows correctly from queue → worker → callback, and that
metadata is properly extracted.

### Testing Utilities (File I/O, etc.)

- Use temp directories for real file operations where possible
- Only mock when simulating failures (OSError, corrupted JSON, etc.)
- Verify actual content, not just "file exists"

### Getting Default Values Dynamically

```python
default_config = AppConfig()  # Don't hardcode defaults
assert config.quality == default_config.quality
```

### Test Structure

- Tests in `tests/unit/` mirror the module structure
- Test classes named after the module/function being tested
- Test methods: `test_<operation>_<expected_result>`
- For retry logic: test `_process_job()` directly, not full `run()` loop
- Use `unittest.mock.AsyncMock` for async functions, `MagicMock` for sync
- Use `@patch` decorator for mocking module-level functions
- Async test methods use pytest-asyncio (`asyncio_mode = "auto"`)
- Don't test framework behavior (dataclass defaults, exception inheritance)

## Special Considerations

### Curses/Textual UI Application
- This is a terminal UI application using Textual
- On Windows, uses `windows-curses` package
- Always restore terminal state on exit
- Screen dimensions may vary - use dynamic sizing

### API Integration
- Uses MangaDex API (https://api.mangadex.org)
- Endpoints: `/manga`, `/manga/{id}/feed`, `/at-home/server`
- Base URLs defined in `src/mangadex_downloader/constants.py`
- Rate limiting implemented via bounded worker pools and semaphores
- Retry logic with exponential backoff and jitter

### Known Issues
- Only supports English translations
- Special characters in manga titles may cause PDF generation issues
- Query parameters in user input may cause unexpected behavior

## Environment Requirements
- Python 3.10+
- Dependencies: aiohttp (speedups), Pillow, windows-curses (Windows), textual
- Dev dependencies: pytest, pytest-asyncio, coverage, ruff, pyright

## Development Workflow
1. Run existing tests to establish baseline
2. Make changes following code style guidelines
3. Run relevant tests, ensure all pass
4. Run `ruff check .` and `ruff format .`
5. Run `poetry run pyright` for type checking
6. Run `coverage report -m` to ensure no regressions
