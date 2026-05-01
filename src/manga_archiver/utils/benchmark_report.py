import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def write_benchmark_report(benchmark_results: dict | None) -> None:
    """Write benchmark results to disk and log aggregate metrics."""
    if not benchmark_results:
        return

    try:
        benchmark_dir = Path("~/.manga-archiver/benchmark").expanduser()
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = benchmark_dir / "metrics.txt"

        with open(metrics_file, "w") as f:
            f.write("Benchmark Results\n")
            f.write("=" * 40 + "\n")
            for key, value in benchmark_results.items():
                if "ms" in key:
                    f.write(f"{key}: {value:.2f} ms\n")
                elif "memory" in key:
                    f.write(f"{key}: {value:.2f} MB\n")
                else:
                    f.write(f"{key}: {value}\n")
    except Exception as e:
        logger.error("Failed to write benchmark file: %s", e)

    logger.info("Aggregate Benchmark Results:")
    for aggregate, value in benchmark_results.items():
        logger.info("[%s]: %s", aggregate, value)
