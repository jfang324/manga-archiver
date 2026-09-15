# Agents Development Guide

Guidelines for agents working on the manga-archiver project.

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

### Code Quality Tools

#### Ruff (Linting & Formatting)

- Lint all files: `ruff check .`
- Lint with auto-fix: `ruff check --fix .`
- Format code: `ruff format .`

#### Pyright (Type Checking)

- Run type checking: `poetry run pyright`

## Project Structure

For the most accurate project layout, see `docs/development.md`.

## Conventions

### Imports

- Source files: relative imports (e.g., `from .mangadex.client import ...`)
- Test files: absolute imports (e.g., `from src.manga_archiver...`)
- Prefer barrel imports from external modules unless being explicit is clearer
- Imports must be top-level. No in-function imports except for a documented architectural reason (e.g., startup optimization)
- Use `TYPE_CHECKING` only when a circular import is proven unresolvable, and never for symbols already imported at module level

### Call Argument Style

- Constructors: use named arguments by default
- Normal function/method calls: prefer positional unless named args improve clarity or prevent mistakes

### Logging

- Always use a module-level logger: `logger = logging.getLogger(__name__)`
- Never use the root logger (`logging.error(...)`) — it loses module context
- Use `%s` formatting, not f-strings: `logger.error("Context: %s", e)`
- Log at system boundaries (entry points, workers); low-level modules raise instead of log

### Error Handling

- Low-level modules raise; consumers decide how to handle it (workers log, UI notifies, ContentProviderManager returns errors in result tuples)
- Model errors with a small exception hierarchy (`NotFoundError(ApiError)`, etc.)

### Defensive Type Narrowing

For unreliable external data (APIs, user input), validate defensively at runtime with `isinstance()` over casts, and raise clear errors on missing fields so the type checker narrows correctly.

### Validation in Types

- Parse external data (API responses, config files) via `from_dict` class methods with fail-fast validation
- Use `frozen=True` for immutable data models

### Docstrings

Google-style, but pragmatic: document public APIs and non-obvious behavior; skip docstrings on test methods and obvious functions; 1-liner for simple things.

### Textual UI

- Build UI in `compose()`, not `on_mount()`
- Prefer reactive properties and built-in widget APIs (e.g., `ListView.index` over manual iteration)
- Communicate via messages (widgets emit, parent handles); don't reach into `query_one()` and guard manually — it throws `NoMatches`
- Remove all dead code when making sweeping revisions

## Testing Patterns

### Core Principles

- **Test behavior, not infrastructure.** Focus on what the code does, not how (queue/thread internals)
- **Never adjust tests to make new code pass.** Change tests only if expected behavior changed
- **No fake tests.** A test must actually run the code under test — don't invoke callbacks manually, don't create a worker without running it, don't mock `queue.get()` and bypass the worker
- **No half-baked assertions.** Verify actual values (`assert config.quality == 75`, `mock_callback.assert_called_once_with(...)`), not just types or existence
- **No pointless tests.** Don't test framework behavior (dataclass defaults, exception inheritance, that `pytest.raises` works)

### Worker Callback Tests

Drive the worker through `_do_work()` with a mocked queue job and assert the callback was invoked with the expected extracted data — proving queue → worker → callback flow.

### Utilities (File I/O)

- Use temp directories for real file operations where possible
- Mock only to simulate failures (OSError, corrupted JSON)
- Verify actual content, not just "file exists"

### Test Structure

- Tests in `tests/unit/` mirror the module structure; classes named after the module/function
- Method naming: `test_<operation>_<expected_result>`
- Use fixtures from `tests/conftest.py` (e.g., `mock_job`, `mock_session`); parameterize with `@pytest.mark.parametrize` for multiple inputs
- For retry logic, test `_process_job()` directly, not the full `run()` loop
- Get defaults dynamically (e.g., `AppConfig()`) instead of hardcoding
- Use `AsyncMock` for async, `MagicMock` for sync; `@patch` for module-level functions
- Async tests use pytest-asyncio (`asyncio_mode = "auto"`)

## Development Workflow

1. Run existing tests to establish baseline
2. Make changes following the conventions above
3. Run relevant tests, ensure all pass
4. Run `ruff check .` and `ruff format .`
5. Run `poetry run pyright` for type checking
6. Run `coverage report -m` to ensure no regressions

## Collaboration

1. **Always outline a plan first** — never jump straight to implementation
2. **Iterate on the plan** — fine-tune until you're confident it will produce the desired result
3. **Implement incrementally** — small, verifiable commits rather than large sweeping changes
