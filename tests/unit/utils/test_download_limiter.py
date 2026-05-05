import asyncio
from dataclasses import dataclass

import pytest

from src.manga_archiver.utils.download_limiter import DownloadLimiter


@dataclass(frozen=True)
class HeldSlot:
    release: asyncio.Event
    task: asyncio.Task[None]


@dataclass(frozen=True)
class AcquireProbe:
    acquired: asyncio.Event
    task: asyncio.Task[None]


class TestDownloadLimiter:
    async def _hold_base_slot(self, limiter: DownloadLimiter) -> HeldSlot:
        acquired = asyncio.Event()
        release = asyncio.Event()

        async def hold_base_slot() -> None:
            async with limiter.acquire():
                acquired.set()
                await release.wait()

        task = asyncio.create_task(hold_base_slot())
        await acquired.wait()

        return HeldSlot(release=release, task=task)

    async def _start_acquire_probe(self, limiter: DownloadLimiter) -> AcquireProbe:
        acquired = asyncio.Event()

        async def probe() -> None:
            async with limiter.acquire():
                acquired.set()

        task = asyncio.create_task(probe())
        await asyncio.sleep(0)

        return AcquireProbe(acquired=acquired, task=task)

    def test_init_rejects_invalid_base_limit(self) -> None:
        with pytest.raises(ValueError, match="base_limit must be greater than 0"):
            DownloadLimiter(base_limit=0)

    def test_init_rejects_invalid_token_ttl(self) -> None:
        with pytest.raises(ValueError, match="token_ttl_seconds must be greater than 0"):
            DownloadLimiter(base_limit=1, token_ttl_seconds=0)

    async def test_acquire_allows_work_inside_context(self) -> None:
        limiter = DownloadLimiter(base_limit=1)
        did_work = False

        async with limiter.acquire():
            did_work = True

        assert did_work is True

    async def test_tokens_expire_after_ttl(self) -> None:
        now = 100.0
        limiter = DownloadLimiter(
            base_limit=1,
            token_ttl_seconds=10.0,
            time_provider=lambda: now,
        )

        await limiter.record_success()
        now = 111.0
        held_slot = await self._hold_base_slot(limiter)
        second_probe = await self._start_acquire_probe(limiter)

        assert second_probe.acquired.is_set() is False

        held_slot.release.set()
        await asyncio.gather(held_slot.task, second_probe.task)

        assert second_probe.acquired.is_set() is True

    async def test_record_retryable_error_clears_tokens(self) -> None:
        limiter = DownloadLimiter(base_limit=1)
        held_slot = await self._hold_base_slot(limiter)

        await limiter.record_success()
        await limiter.record_success()
        await limiter.record_retryable_error()

        second_probe = await self._start_acquire_probe(limiter)

        assert second_probe.acquired.is_set() is False

        held_slot.release.set()
        await asyncio.gather(held_slot.task, second_probe.task)

        assert second_probe.acquired.is_set() is True

    async def test_acquire_waits_when_base_is_full_without_tokens(self) -> None:
        limiter = DownloadLimiter(base_limit=1)
        held_slot = await self._hold_base_slot(limiter)
        second_probe = await self._start_acquire_probe(limiter)

        assert second_probe.acquired.is_set() is False

        held_slot.release.set()
        await asyncio.gather(held_slot.task, second_probe.task)

        assert second_probe.acquired.is_set() is True

    async def test_acquire_spends_token_for_burst_slot_when_base_is_full(self) -> None:
        limiter = DownloadLimiter(base_limit=1)
        held_slot = await self._hold_base_slot(limiter)

        await limiter.record_success()

        burst_probe = await self._start_acquire_probe(limiter)
        await burst_probe.task

        assert burst_probe.acquired.is_set() is True

        held_slot.release.set()
        await held_slot.task
