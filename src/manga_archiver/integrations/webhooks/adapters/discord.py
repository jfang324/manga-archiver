from .types import WebhookRequest

DISCORD_WEBHOOK_SUCCESS_STATUS = 204


class DiscordWebhookAdapter:
    """Adapter for Discord webhook request data."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def build_request(self, message: str) -> WebhookRequest:
        """Build Discord webhook request data."""
        return WebhookRequest(
            url=self._webhook_url,
            payload={"content": message},
            success_status=DISCORD_WEBHOOK_SUCCESS_STATUS,
        )
