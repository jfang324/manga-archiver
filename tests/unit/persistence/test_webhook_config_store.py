import json
from pathlib import Path
from uuid import uuid4

from src.manga_archiver.integrations.webhooks import WebhookProvider
from src.manga_archiver.persistence.webhook_config_store import WebhookConfigStore


async def test_load_skips_invalid_webhook_config_entries() -> None:
    config_dir = Path(".pytest_cache") / "webhook_config_store"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{uuid4()}.json"
    try:
        config_path.write_text(
            json.dumps(
                {
                    "discord": {"enabled": True, "webhook_url": "https://example.com/webhook"},
                    "unsupported": {
                        "enabled": True,
                        "webhook_url": "https://example.com/other",
                    },
                    "broken": {"enabled": "yes", "webhook_url": "https://example.com/broken"},
                }
            )
        )
        store = WebhookConfigStore(config_path)

        config = await store.load()
    finally:
        config_path.unlink(missing_ok=True)

    assert config == {
        WebhookProvider.DISCORD: {
            "enabled": True,
            "webhook_url": "https://example.com/webhook",
        }
    }
