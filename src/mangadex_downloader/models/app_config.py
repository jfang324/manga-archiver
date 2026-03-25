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
    """
    A data container for the applications configuration.

    Attributes:
        output_path (Path): The path to the output directory.
        quality (int): The quality of the output PDF file (1-100).
        optimize (bool): Whether to optimize the PDF file size.
        output_format (OutputFormat): The output format of the PDF file (PDF).
        data_saver (bool): Whether to download lower quality images.
    """

    optimize: bool
    data_saver: bool

    # Properties that require validation
    _output_path: Path
    _quality: int
    _output_format: OutputFormat

    def __post_init__(self):
        """Trigger validators post init for fields that require it."""
        self.output_path = self._output_path
        self.quality = self._quality
        self.output_format = self._output_format

    @property
    def output_path(self) -> Path:
        """Public output_path property."""
        return self._output_path

    @output_path.setter
    def output_path(self, value: Path):
        """Validate and set output_path property."""
        if not value.exists():
            raise ValueError(f"output_path does not exist: {value}")

        if not value.is_dir():
            raise ValueError(f"output_path is not a directory: {value}")

        self._output_path = value

    @property
    def quality(self) -> int:
        """Public quality property."""
        return self._quality

    @quality.setter
    def quality(self, value: int):
        """Validate and set quality property."""
        if value < 1 or value > 100:
            raise ValueError(f"quality must be between 1 and 100: {value}")

        self._quality = value

    @property
    def output_format(self) -> OutputFormat:
        """Public output_format property."""
        return self._output_format

    @output_format.setter
    def output_format(self, value: OutputFormat):
        """Validate and set output_format property."""
        if value not in OutputFormat:
            raise ValueError(f"output_format is not supported: {value}")

        self._output_format = value
