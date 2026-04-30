from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimePreset:
    """Curated runtime tuning values for common throughput profiles."""

    name: str
    description: str
    resolve_workers: int
    download_workers: int
    merge_workers: int
    resolve_rate_limit: int
    download_rate_limit: int
    queue_size: int


PRESETS: dict[str, RuntimePreset] = {
    "safe": RuntimePreset(
        name="safe",
        description="Near-serial, maximum reliability for weak machines or flaky networks.",
        resolve_workers=1,
        download_workers=1,
        merge_workers=1,
        resolve_rate_limit=1,
        download_rate_limit=1,
        queue_size=1,
    ),
    "slow": RuntimePreset(
        name="slow",
        description="Slow configuration with low peak memory usage and high reliability.",
        resolve_workers=2,
        download_workers=2,
        merge_workers=2,
        resolve_rate_limit=5,
        download_rate_limit=5,
        queue_size=2,
    ),
    "fast": RuntimePreset(
        name="fast",
        description="Very high throughput with potential for very high memory usage and dropped downloads.",
        resolve_workers=4,
        download_workers=4,
        merge_workers=4,
        resolve_rate_limit=10,
        download_rate_limit=20,
        queue_size=8,
    ),
}


def get_preset(name: str) -> RuntimePreset:
    """Return a preset by name."""
    return PRESETS[name]


def get_preset_names() -> tuple[str, ...]:
    """Return preset names in display order."""
    return tuple(PRESETS)


def iter_presets() -> tuple[RuntimePreset, ...]:
    """Return presets in display order."""
    return tuple(PRESETS.values())


def format_presets() -> str:
    """Format available presets for CLI output."""
    lines = ["Available presets:", ""]

    for preset in iter_presets():
        lines.append(f"{preset.name}")
        lines.append(f"  {preset.description}")
        lines.append(
            "  "
            f"resolve_workers={preset.resolve_workers}, "
            f"download_workers={preset.download_workers}, "
            f"merge_workers={preset.merge_workers}, "
            f"resolve_rate_limit={preset.resolve_rate_limit}, "
            f"download_rate_limit={preset.download_rate_limit}, "
            f"queue_size={preset.queue_size}"
        )

    return "\n".join(lines)
