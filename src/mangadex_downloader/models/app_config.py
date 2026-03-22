from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """
    A data container for the applications configuration.

    Attributes:
        output_path (Path): The path to the output directory.
        quality (int): The quality of the output PDF file (1-100).
        optimize (bool): Whether to optimize the PDF file size.
        output_format (str): The output format of the PDF file (PDF).
        data_saver (bool): Whether to download lower quality images.
    """

    output_path: Path
    quality: int
    optimize: bool
    output_format: str
    data_saver: bool
