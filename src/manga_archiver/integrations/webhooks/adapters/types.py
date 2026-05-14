from dataclasses import dataclass
from typing import Protocol, TypeAlias

WebhookPayload: TypeAlias = dict[str, object]


@dataclass(frozen=True)
class WebhookRequest:
    """Webhook request data produced by an integration adapter."""

    url: str
    payload: WebhookPayload
    success_status: int


class WebhookAdapter(Protocol):
    """Structural contract for webhook integration adapters."""

    def build_request(self, message: str) -> WebhookRequest:
        """Build integration-specific webhook request data."""
        ...
