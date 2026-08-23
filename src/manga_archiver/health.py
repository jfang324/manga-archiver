import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from aiohttp import ClientError, ClientSession

from .integrations.content_providers.allanime.client import AllMangaClient
from .integrations.content_providers.base import Provider
from .integrations.content_providers.mangadex.client import MangaDexApiClient
from .integrations.exceptions import BadGatewayError, RateLimitError
from .models import Chapter, ContentSource, DownloadResource, Manga

HEALTH_CHECK_QUERIES: tuple[str, ...] = (
    "One Piece",
    "Naruto",
    "Solo Leveling",
    "Bleach",
)
HEALTH_CHECK_PAGE = 1
HEALTH_CHECK_PAGE_SIZE = 5
HEALTH_CHECK_DOWNLOAD_CANDIDATES = 3
HEALTH_CHECK_DOWNLOAD_ATTEMPTS = 3
HEALTH_CHECK_RETRY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class HealthCheckChapterCandidate:
    """Candidate chapter selected during health probing."""

    manga_title: str
    chapter: Chapter


class HealthStepStatus(Enum):
    """Status for a single healthcheck step."""

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class HealthStepResult:
    """Result for one provider healthcheck step."""

    name: str
    status: HealthStepStatus
    detail: str
    elapsed_ms: int | None = None


@dataclass(frozen=True)
class ProviderHealthCheckResult:
    """Healthcheck result for one content provider."""

    source: ContentSource
    search: HealthStepResult
    chapters: HealthStepResult
    download_resource: HealthStepResult

    @property
    def is_healthy(self) -> bool:
        """Return whether the provider reached download-resource success."""
        return self.download_resource.status == HealthStepStatus.OK


class ProviderHealthChecker:
    """Runs live healthchecks against content provider APIs."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize provider clients."""
        self._providers: dict[ContentSource, Provider] = {
            ContentSource.MANGADEX: MangaDexApiClient(session),
            ContentSource.ALLMANGA: AllMangaClient(session),
        }

    async def check_all_completed(self) -> AsyncIterator[ProviderHealthCheckResult]:
        """Yield provider results as each check completes."""
        tasks = [
            asyncio.create_task(self.check_provider(source, provider))
            for source, provider in self._providers.items()
        ]

        for task in asyncio.as_completed(tasks):
            yield await task

    async def check_provider(
        self, source: ContentSource, provider: Provider
    ) -> ProviderHealthCheckResult:
        """Check search, chapter lookup, and download resource retrieval.

        Tries each candidate query in HEALTH_CHECK_QUERIES in order, returning
        the first one whose chain reaches download-resource success. When every
        query fails, returns the last attempt's result so callers see the most
        recent error rather than an aggregate.
        """
        last_result: ProviderHealthCheckResult | None = None
        for query in HEALTH_CHECK_QUERIES:
            result = await self._check_provider_with_query(source, provider, query)
            if result.download_resource.status == HealthStepStatus.OK:
                return result
            last_result = result
        if last_result is None:
            return ProviderHealthCheckResult(
                source=source,
                search=self._skipped_step("search", "no health check queries configured"),
                chapters=self._skipped_step("chapters", "no health check queries configured"),
                download_resource=self._skipped_step(
                    "download_resource", "no health check queries configured"
                ),
            )
        return last_result

    async def _check_provider_with_query(
        self, source: ContentSource, provider: Provider, query: str
    ) -> ProviderHealthCheckResult:
        """Run search → chapters → download for a single health-check query."""
        skipped_download_resource = self._skipped_step(
            "download_resource", "chapters did not produce a usable chapter"
        )

        search_step, manga_results = await self._check_search(provider, query)
        if not manga_results:
            return ProviderHealthCheckResult(
                source=source,
                search=search_step,
                chapters=self._skipped_step("chapters", "search did not produce a usable manga"),
                download_resource=skipped_download_resource,
            )

        chapters_step, chapter_candidates = await self._check_chapters(provider, manga_results)
        if not chapter_candidates:
            return ProviderHealthCheckResult(
                source=source,
                search=search_step,
                chapters=chapters_step,
                download_resource=skipped_download_resource,
            )

        download_resource_step = await self._check_download_resource(provider, chapter_candidates)
        return ProviderHealthCheckResult(
            source=source,
            search=search_step,
            chapters=chapters_step,
            download_resource=download_resource_step,
        )

    async def _check_search(
        self, provider: Provider, query: str
    ) -> tuple[HealthStepResult, list[Manga]]:
        start_ns = time.perf_counter_ns()
        try:
            manga_results = await provider.search_manga(
                query,
                HEALTH_CHECK_PAGE,
                HEALTH_CHECK_PAGE_SIZE,
            )
        except Exception as e:
            return self._failed_step("search", start_ns, e), []

        usable_manga = [result for result in manga_results if result.id]
        if not usable_manga:
            return (
                self._ok_step(
                    "search",
                    start_ns,
                    f"no usable manga found for query '{query}'",
                ),
                [],
            )

        return self._ok_step(
            "search", start_ns, f"found {len(usable_manga)} usable results for query '{query}'"
        ), usable_manga

    async def _check_chapters(
        self, provider: Provider, manga_results: list[Manga]
    ) -> tuple[HealthStepResult, list[HealthCheckChapterCandidate]]:
        start_ns = time.perf_counter_ns()
        last_error: Exception | None = None
        candidates: list[HealthCheckChapterCandidate] = []

        for manga in manga_results:
            try:
                chapters = await provider.get_chapters(manga.id)
            except Exception as e:
                last_error = e
                continue

            candidates.extend(
                HealthCheckChapterCandidate(manga_title=manga.title, chapter=chapter)
                for chapter in chapters
                if chapter.id
            )

        if not candidates:
            if last_error is not None:
                return self._failed_step("chapters", start_ns, last_error), []

            return self._ok_step("chapters", start_ns, "no usable chapter found"), []

        selected_candidates = candidates[:HEALTH_CHECK_DOWNLOAD_CANDIDATES]
        return (
            self._ok_step(
                "chapters",
                start_ns,
                (
                    f"selected {len(selected_candidates)} of "
                    f"{len(candidates)} usable chapter candidates"
                ),
            ),
            selected_candidates,
        )

    async def _check_download_resource(
        self, provider: Provider, candidates: list[HealthCheckChapterCandidate]
    ) -> HealthStepResult:
        start_ns = time.perf_counter_ns()
        last_error: Exception | None = None

        for candidate in candidates:
            try:
                download_resource = await self._get_download_resource_with_retry(
                    provider, candidate.chapter.id
                )
            except Exception as e:
                last_error = e
                continue

            return self._ok_step(
                "download_resource",
                start_ns,
                (
                    f"selected {candidate.manga_title} chapter "
                    f"{candidate.chapter.chapter_num}: {len(download_resource.urls)} urls"
                ),
            )

        if last_error is not None:
            return self._failed_step("download_resource", start_ns, last_error)

        return self._ok_step("download_resource", start_ns, "no candidate chapters to check")

    async def _get_download_resource_with_retry(
        self, provider: Provider, chapter_id: str
    ) -> DownloadResource:
        last_error: Exception | None = None

        for attempt in range(HEALTH_CHECK_DOWNLOAD_ATTEMPTS):
            try:  # PERF203: retry loop is intentional for transient provider failures
                return await provider.get_download_resource(chapter_id)
            except (  # noqa: PERF203
                RateLimitError,
                BadGatewayError,
                TimeoutError,
                asyncio.TimeoutError,
                ClientError,
            ) as e:
                last_error = e
                if attempt < HEALTH_CHECK_DOWNLOAD_ATTEMPTS - 1:
                    await asyncio.sleep(HEALTH_CHECK_RETRY_DELAY_SECONDS)

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            f"Download resource check failed after {HEALTH_CHECK_DOWNLOAD_ATTEMPTS} attempts"
        )

    def _ok_step(self, name: str, start_ns: int, detail: str) -> HealthStepResult:
        return HealthStepResult(
            name=name,
            status=HealthStepStatus.OK,
            elapsed_ms=self._elapsed_ms(start_ns),
            detail=detail,
        )

    def _failed_step(self, name: str, start_ns: int, error: Exception) -> HealthStepResult:
        return HealthStepResult(
            name=name,
            status=HealthStepStatus.FAILED,
            elapsed_ms=self._elapsed_ms(start_ns),
            detail=f"{type(error).__name__}: {error}",
        )

    def _skipped_step(self, name: str, detail: str) -> HealthStepResult:
        return HealthStepResult(
            name=name,
            status=HealthStepStatus.SKIPPED,
            detail=detail,
        )

    def _elapsed_ms(self, start_ns: int) -> int:
        return (time.perf_counter_ns() - start_ns) // 1_000_000


def format_provider_health_check_result(result: ProviderHealthCheckResult) -> str:
    """Format one provider healthcheck result for terminal output."""
    return "\n".join(
        [
            str(result.source),
            f"  {format_health_step(result.search)}",
            f"  {format_health_step(result.chapters)}",
            f"  {format_health_step(result.download_resource)}",
        ]
    )


def format_health_step(step: HealthStepResult) -> str:
    """Format one healthcheck step."""
    if step.elapsed_ms is None:
        return f"{step.name}: {step.status.value} - {step.detail}"

    return f"{step.name}: {step.status.value} ({step.elapsed_ms} ms) - {step.detail}"
