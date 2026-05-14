from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

from aiohttp import ClientSession

from ..exceptions import ApiError, BadGatewayError, NotFoundError, RateLimitError
from .adapters import DiscordWebhookAdapter
from .adapters.types import WebhookAdapter, WebhookRequest
from .types import WebhookProvider

if TYPE_CHECKING:
    from ...persistence.webhook_config_store import WebhookConfigs

WebhookAdapterFactory: TypeAlias = Callable[[str], WebhookAdapter]

WEBHOOK_ADAPTERS: dict[WebhookProvider, WebhookAdapterFactory] = {
    WebhookProvider.DISCORD: DiscordWebhookAdapter,
}


class WebhookClient:
    """Orchestrates enabled webhook integrations."""

    def __init__(
        self,
        session: ClientSession,
        providers: list[WebhookProvider],
        config: WebhookConfigs,
    ) -> None:
        self._session = session
        self._enabled_providers = providers
        self._adapters = self._build_adapters(config)

    async def notify(self, message: str) -> None:
        """Notify all enabled webhook integrations."""
        requests = [
            (provider, self._adapters[provider].build_request(message))
            for provider in self._enabled_providers
            if provider in self._adapters
        ]
        if not requests:
            return

        await asyncio.gather(
            *[
                self._send_request(provider, webhook_request)
                for provider, webhook_request in requests
            ],
        )

    def _build_adapters(
        self,
        config: WebhookConfigs,
    ) -> dict[WebhookProvider, WebhookAdapter]:
        """Build adapters for configured webhook providers."""
        adapters: dict[WebhookProvider, WebhookAdapter] = {}

        for provider in WebhookProvider:
            adapter_type = WEBHOOK_ADAPTERS.get(provider)
            if adapter_type is None:
                continue

            provider_config = config.get(provider)
            if provider_config is None or not provider_config["webhook_url"].strip():
                continue

            adapters[provider] = adapter_type(provider_config["webhook_url"])

        return adapters

    async def _send_request(
        self,
        provider: WebhookProvider,
        webhook_request: WebhookRequest,
    ) -> None:
        async with self._session.post(
            webhook_request.url,
            json=webhook_request.payload,
        ) as response:
            if response.status == webhook_request.success_status:
                return

            if response.status == 400:
                raise ApiError(f"{provider.value.title()} webhook rejected the request")

            if response.status == 404:
                raise NotFoundError(f"{provider.value.title()} webhook was not found")

            if response.status == 429:
                raise RateLimitError(f"{provider.value.title()} webhook rate limit exceeded")

            if response.status == 502:
                raise BadGatewayError(f"{provider.value.title()} webhook gateway error")

            if response.status == 500:
                raise ApiError(f"{provider.value.title()} webhook server error")

            raise ApiError(
                f"{provider.value.title()} webhook returned unexpected status {response.status}"
            )
