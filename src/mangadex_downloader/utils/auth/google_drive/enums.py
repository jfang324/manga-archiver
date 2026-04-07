from enum import Enum


class GoogleAuthDeviceFlowResult(Enum):
    """Enum for Google OAuth device flow result codes."""

    AUTHORIZATION_PENDING = "authorization_pending"
    SLOW_DOWN = "slow_down"
    ACCESS_DENIED = "access_denied"
    EXPIRED_TOKEN = "expired_token"  # noqa: S105
    TIMEOUT = "timeout"
