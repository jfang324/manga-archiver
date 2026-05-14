import asyncio
import json
from pathlib import Path
from typing import TypedDict

from ..integrations.webhooks import WebhookProvider
from .utils import get_root_path
from .validation import require_mapping, required_bool, required_str

WEBHOOK_CONFIG_FILENAME = "webhooks.json"


class WebhookConfig(TypedDict):
    """Persisted webhook provider settings."""

    enabled: bool
    webhook_url: str


WebhookConfigs = dict[WebhookProvider, WebhookConfig]


class WebhookConfigStore:
    """Persists webhook integration settings between sessions."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or get_root_path() / WEBHOOK_CONFIG_FILENAME

    async def load(self) -> WebhookConfigs:
        """Load webhook configuration."""
        if not await asyncio.to_thread(self._config_path.exists):
            return {}

        try:
            parsed_config = json.loads(await asyncio.to_thread(self._config_path.read_text))
        except (json.JSONDecodeError, OSError):
            return {}

        try:
            return _parse_webhook_configs(parsed_config)
        except ValueError:
            return {}

    async def save_config(self, provider: WebhookProvider, provider_config: WebhookConfig) -> None:
        """Save webhook configuration."""
        _validate_webhook_config(provider_config)
        config = await self.load()
        config[provider] = provider_config
        serialized_config = {
            webhook_provider.value: webhook_config
            for webhook_provider, webhook_config in config.items()
        }

        try:
            await asyncio.to_thread(self._config_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(
                self._config_path.write_text,
                json.dumps(serialized_config, indent=2),
            )
        except OSError as e:
            raise ValueError(f"Failed to save {WEBHOOK_CONFIG_FILENAME}: {e}") from e

    def get_enabled_webhooks(self, config: WebhookConfigs) -> list[WebhookProvider]:
        """Return enabled webhook integrations from persisted config."""
        return [
            provider
            for provider, provider_config in config.items()
            if provider_config["enabled"] and provider_config["webhook_url"].strip()
        ]


def _parse_webhook_config(raw_config: object) -> WebhookConfig:
    webhook_config = require_mapping(raw_config, "webhook config")
    return WebhookConfig(
        enabled=required_bool(webhook_config, "enabled"),
        webhook_url=required_str(webhook_config, "webhook_url"),
    )


def _parse_webhook_configs(raw_config: object) -> WebhookConfigs:
    raw_configs = require_mapping(raw_config, "webhook config")
    configs: WebhookConfigs = {}

    for raw_provider, raw_provider_config in raw_configs.items():
        provider = WebhookProvider(str(raw_provider))
        configs[provider] = _parse_webhook_config(raw_provider_config)

    return configs


def _validate_webhook_config(webhook_config: WebhookConfig) -> None:
    try:
        parsed_config = _parse_webhook_config(webhook_config)
    except ValueError as e:
        raise ValueError(f"Invalid webhook config: {e}") from e

    if parsed_config["enabled"] and not parsed_config["webhook_url"].strip():
        raise ValueError("Invalid webhook config: webhook_url cannot be empty")
