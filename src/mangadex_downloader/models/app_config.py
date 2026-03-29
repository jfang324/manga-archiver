from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class OutputFormat(Enum):
    """
    An enum class for the supported output formats.
    """

    PDF = "pdf"
    CBZ = "cbz"
    EPUB = "epub"

    def __str__(self) -> str:
        """Return the string representation for ease of use."""
        return self.value

    @classmethod
    def list_formats(cls) -> list[str]:
        """Return a list of the supported output formats."""
        return [format.value for format in cls]


@dataclass
class AppConfig:
    """Application configuration with validation.

    Attributes:
        optimize: Whether to optimize output file size
        data_saver: Whether to download lower quality images
        output_path: The directory to save output files (validated)
        quality: The quality setting for output (1-100, validated)
        output_format: The output format (PDF, CBZ, etc., validated)
    """

    optimize: bool
    data_saver: bool

    # Properties that require validation
    _output_path: Path
    _quality: int
    _output_format: OutputFormat

    def __post_init__(self):
        """Initialize validated properties."""
        self.output_path = self._output_path
        self.quality = self._quality
        self.output_format = self._output_format

    @property
    def output_path(self) -> Path:
        """The output directory path."""
        return self._output_path

    @output_path.setter
    def output_path(self, value: Path):
        """Set output path with validation."""
        if not value.exists():
            raise ValueError(f"output_path does not exist: {value}")

        if not value.is_dir():
            raise ValueError(f"output_path is not a directory: {value}")

        self._output_path = value

    @property
    def quality(self) -> int:
        """The quality setting (1-100)."""
        return self._quality

    @quality.setter
    def quality(self, value: int):
        """Set quality with validation."""
        if value < 1 or value > 100:
            raise ValueError(f"quality must be between 1 and 100: {value}")

        self._quality = value

    @property
    def output_format(self) -> OutputFormat:
        """The output format."""
        return self._output_format

    @output_format.setter
    def output_format(self, value: OutputFormat):
        """Set output format with validation."""
        if value not in OutputFormat:
            raise ValueError(f"output_format is not supported: {value}")

        self._output_format = value
