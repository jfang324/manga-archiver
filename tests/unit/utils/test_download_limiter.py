import asyncio

import pytest

from src.manga_archiver.utils.download_limiter import StaticDownloadLimiter


class TestStaticDownloadLimiter:
    @pytest.mark.parametrize("limit", [0, -1], ids=["zero", "negative"])
    def test_init_rejects_invalid_limit(self, limit: int) -> None:
        with pytest.raises(ValueError, match="limit must be greater than 0"):
            StaticDownloadLimiter(limit)

    async def test_acquire_allows_work_inside_context(self) -> None:
        limiter = StaticDownloadLimiter(1)
        did_work = False

        async with limiter.acquire():
            did_work = True

        assert did_work is True

    async def test_acquire_enforces_concurrency_limit(self) -> None:
        limiter = StaticDownloadLimiter(1)
        first_acquired = asyncio.Event()
        release_first = asyncio.Event()
        second_acquired = False

        async def hold_first_slot() -> None:
            async with limiter.acquire():
                first_acquired.set()
                await release_first.wait()

        async def wait_for_second_slot() -> None:
            nonlocal second_acquired

            async with limiter.acquire():
                second_acquired = True

        first_task = asyncio.create_task(hold_first_slot())
        await first_acquired.wait()

        second_task = asyncio.create_task(wait_for_second_slot())
        await asyncio.sleep(0)

        assert second_acquired is False

        release_first.set()
        await asyncio.gather(first_task, second_task)

        assert second_acquired is True
