from enum import Enum


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
