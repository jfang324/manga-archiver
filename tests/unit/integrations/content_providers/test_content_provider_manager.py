import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.integrations.content_providers import ContentProviderManager
from src.manga_archiver.models import ContentSource, DownloadResource


class TestContentProviderManagerDownloadResource:
    def _create_manager(self) -> ContentProviderManager:
        manager = ContentProviderManager(MagicMock())
        manager._providers = {
            ContentSource.ALLMANGA: MagicMock(),
        }
        manager._resolve_semaphores = {
            ContentSource.ALLMANGA: asyncio.Semaphore(1),
        }
        manager._page_cache = MagicMock()
        return manager

    @pytest.mark.asyncio
    async def test_get_download_resource_fetches_provider_when_cache_get_fails(self) -> None:
        manager = self._create_manager()
        provider = manager._providers[ContentSource.ALLMANGA]
        provider.get_download_resource = AsyncMock(
            return_value=DownloadResource(
                urls=["http://example.com/1.jpg"],
                source=ContentSource.ALLMANGA,
            )
        )
        manager._page_cache.get = AsyncMock(side_effect=RuntimeError("cache unavailable"))
        manager._page_cache.set = AsyncMock()

        result = await manager.get_download_resource(ContentSource.ALLMANGA, "manga:1")

        assert result.urls == ["http://example.com/1.jpg"]
        provider.get_download_resource.assert_awaited_once_with("manga:1")

    @pytest.mark.asyncio
    async def test_get_download_resource_returns_provider_result_when_cache_set_fails(
        self,
    ) -> None:
        manager = self._create_manager()
        provider = manager._providers[ContentSource.ALLMANGA]
        provider.get_download_resource = AsyncMock(
            return_value=DownloadResource(
                urls=["http://example.com/1.jpg"],
                source=ContentSource.ALLMANGA,
            )
        )
        manager._page_cache.get = AsyncMock(return_value=None)
        manager._page_cache.set = AsyncMock(side_effect=RuntimeError("cache unavailable"))

        result = await manager.get_download_resource(ContentSource.ALLMANGA, "manga:1")

        assert result.urls == ["http://example.com/1.jpg"]
        manager._page_cache.set.assert_awaited_once_with(
            ContentSource.ALLMANGA,
            "manga:1",
            ["http://example.com/1.jpg"],
        )

    @pytest.mark.asyncio
    async def test_invalidate_cache_ignores_cache_delete_failure(self) -> None:
        manager = self._create_manager()
        manager._page_cache.delete = AsyncMock(side_effect=RuntimeError("cache unavailable"))

        await manager.invalidate_cache(ContentSource.ALLMANGA, "manga:1")

        manager._page_cache.delete.assert_awaited_once_with(ContentSource.ALLMANGA, "manga:1")
