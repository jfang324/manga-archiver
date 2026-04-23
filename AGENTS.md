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
- Run a single test file: `coverage run -m pytest tests/unit/workers/test_download_worker.py -v`
- Run a specific test class: `coverage run -m pytest tests/unit/workers/test_download_worker.py::TestDownload -v`
- Run a specific test method: `coverage run -m pytest tests/unit/workers/test_download_worker.py::TestDownload::test_fetch_success_returns_json -v`
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
- Python version: 3.10

## Project Structure
```
manga-archiver/
├── src/manga_archiver/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── app.py                  # Main Textual application
│   ├── backlog_sync.py
│   ├── pipeline_manager.py
│   ├── cli/
│   ├── constants/
│   ├── db/
│   │   └── migrations/
│   ├── integrations/
│   │   ├── exceptions.py
│   │   ├── content_providers/  # MangaDex, AnimeLab
│   │   └── storage_providers/ # Google Drive
│   ├── models/
│   ├── repositories/
│   ├── screens/
│   ├── utils/
│   │   └── auth/
│   ├── widgets/
│   └── workers/
├── tests/
│   └── unit/                   # Mirrors source structure
│       ├── workers/
│       ├── widgets/
│       ├── utils/
│       │   └── auth/
│       ├── integrations/
│       │   ├── mangadex/
│       │   ├── Allanime/
│       │   └── storage_providers/
│       ├── db/
│       └── test_pipeline_manager.py
├── pyproject.toml
└── README.md
```

## Code Style Guidelines

### Imports
- Source files: use relative imports (e.g., `from .mangadex.client import ...`)
- Test files: use absolute imports (e.g., `from src.manga_archiver...`)
- When importing from external modules, prefer barrel imports unless being explicit makes sense
- Order: standard library → third-party → local imports
- Multiple imports per line are fine as long as they are from the same module/file

### Barrel Exports

Keep `__init__.py` barrel exports minimal - only expose what is considered the stable public API. This prevents circular dependency issues as the codebase grows.

```python
# ✅ GOOD - Minimal stable public API
from .client import MangaDexApiClient  # Main client only
from .exceptions import NotFoundError, RateLimitError  # Required exceptions

# ❌ BAD - Exposing internal modules
from .submodule.internal import helper_function  # Leaks internal details
```

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
- Use TypeAlias for complex types (e.g., tuple return types)
- Explicitly annotate `__init__` with `-> None`

```python
from typing import TypeAlias

SearchResults: TypeAlias = tuple[list[Manga], list[tuple[ContentSource, Exception]]]


def __init__(self, session: ClientSession) -> None:
    """Initialize the client."""
```

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

**Core Principle: Low-level modules raise, don't log.**

Modules should be self-contained and not log — consumers handle logging appropriately for their context.

**Exception hierarchy:**

```python
# integrations/exceptions.py
class ApiError(Exception):
    """Raised for general API errors."""


class NotFoundError(ApiError):
    """Raised when a requested resource is not found (404)."""


class RateLimitError(ApiError):
    """Raised when the API rate limit is exceeded (429)."""


class BadGatewayError(ApiError):
    """Raised when the API returns a 502 Bad Gateway error."""
```

```python
# In low-level modules - raise exceptions, don't log
try:
    response = await self._request(url, params)
except (NotFoundError, RateLimitError, BadGatewayError) as e:
    raise  # Bare raise preserves traceback
```

**In ContentProviderManager:**
- Methods return errors in result tuples for parallel operations (e.g., `search_manga` returns `(results, errors)`)
- Single-provider methods raise exceptions (`ValueError` for invalid source, API errors for failures)

**In Consumers (workers, UI):**
- Handle errors appropriately for context
- Workers log errors for audit trail
- UI shows user-friendly notifications

```python
# Worker handles background errors - logs for debugging
try:
    await self._process_job(job)
except Exception as e:
    logger.error("Job failed: %s", e)  # Log in worker
    await self._send_notification(job, JobStatus.FAILED)

# UI handles foreground errors - shows notification
try:
    results = await client.search_manga(query)
except RateLimitError:
    self.notify("Too many requests. Please wait.")
except (NotFoundError, ApiError):
    self.notify("Error searching for manga")
```

### Defensive Type Narrowing

When working with unreliable external data (APIs, user input), be highly defensive:

```python
# Use isinstance() for runtime validation
if isinstance(job, ResolveJob):
    manga_feed = job.manga_feed
    if manga_feed is None:
        raise ValueError("Job missing manga_feed")
    # Now type checker knows manga_feed is not None
    chapters = [c for c in manga_feed if isinstance(c, Chapter)]
```

Use `isinstance()` over casts — provides runtime validation with clear error messages.

### Logging at Boundaries Only

Log errors at system boundaries where they can be usefully captured:
- Entry point (startup, shutdown, uncaught errors)
- Workers (background task audit trail)
- NOT in low-level modules (API clients, managers, utilities)

```python
# Entry point - catches unhandled errors
async def main():
    try:
        await app.run()
    except Exception as e:
        logger.critical("Fatal error: %s", e)  # Log at boundary
        raise
```

### Validation in Types

Use `from_dict` methods with fail-fast validation:

```python
@dataclass(frozen=True)
class SearchResult:
    _id: str

    @classmethod
    def from_dict(cls, data: dict) -> SearchResult:
        if "_id" not in data:
            raise ValueError("Invalid result: missing _id")
        return cls(_id=data["_id"])
```

**Dataclass patterns:**
- Use `frozen=True` for immutable data models
- Use `from_dict` class methods for parsing external data (API responses, config files)
- Fail-fast with clear error messages in validation

```python
@dataclass(frozen=True)
class Chapter:
    id: str
    number: float
    title: str | None

    @classmethod
    def from_dict(cls, data: dict) -> Chapter:
        if "id" not in data:
            raise ValueError("Chapter missing required field: id")
        return cls(
            id=data["id"],
            number=data.get("number", 0.0),
            title=data.get("title"),
        )
```

## Code Quality Standards

Target quality level for new code: **9/10**

This means:
- Build UI in `compose()`, not in `on_mount()`
- Use reactive properties and built-in widget APIs (e.g., `ListView.index` instead of manual iteration)
- Modern type hints: use `int | None` instead of `Union[int, None]`
- Minimal, focused methods with single responsibility
- Proper message-based communication (widgets emit messages, parent handles actions)
- No redundant validation (e.g., don't manually check if `query_one()` found widgets - it throws `NoMatches`)
- Be highly defensive with type narrowing when working with unreliable external data (APIs, user input)
- Remove all dead code when making sweeping revisions

## Async/Await Patterns
- All I/O operations use async/await
- Use `asyncio.gather()` for concurrent operations
- Always pass session objects to async functions
- Never block the event loop with synchronous operations

## Service Architecture
- All services in `src/manga_archiver/` (grouped by function)
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

**Never adjust tests to make new code pass.** Only change tests if the expected behavior is supposed to have changed.

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
- Test methods: `test_<operation>_<expected_result>` (e.g., `test_fetch_success_returns_json`)
- Use fixtures from `tests/conftest.py` where available (e.g., `mock_job`, `mock_session`)
- Parameterize tests with `@pytest.mark.parametrize` when testing multiple inputs
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
- Content Providers: MangaDex, AnimeLab
- Storage Providers: Google Drive
- Base URLs defined in `src/manga_archiver/constants.py`
- Rate limiting implemented via bounded worker pools and semaphores
- Retry logic with exponential backoff and jitter

### Known Issues
- Only supports English translations
- Special characters in manga titles may cause PDF generation issues
- Query parameters in user input may cause unexpected behavior

## Environment Requirements
- Python 3.10+
- Dependencies: aiohttp (speedups), Pillow, textual, google-auth, google-api-python-client, ebooklib, cryptography
- Dev dependencies: pytest, pytest-asyncio, coverage, ruff, pyright, pre-commit

## Development Workflow
1. Run existing tests to establish baseline
2. Make changes following code style guidelines
3. Run relevant tests, ensure all pass
4. Run `ruff check .` and `ruff format .`
5. Run `poetry run pyright` for type checking
6. Run `coverage report -m` to ensure no regressions

## Collaboration

When working together on a task:
1. **Always outline a plan first** — never jump straight to implementation
2. **Iterate on the plan** — we'll fine-tune until you're confident it will produce the desired result
3. **Implement incrementally** — small, verifiable commits rather than large sweeping changes
