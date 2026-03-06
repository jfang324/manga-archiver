"""PDF generation utilities."""

import os
from io import BytesIO
from typing import Optional

from PIL import Image


class PdfGenerator:
    """Generator for creating PDF files from images."""

    def __init__(
        self, quality: int = 75, optimize: bool = False
    ) -> None:
        """Initialize the PDF generator.

        :param quality: PDF quality (1-100, default: 75)
        :param optimize: Whether to optimize PDF file size (default: False)
        """
        self._quality = quality
        self._optimize = optimize

    def generate(
        self,
        image_data_list: list[bytes],
        output_name: str,
        output_path: Optional[str] = None,
    ) -> None:
        """Generate a PDF file from the image data list.

        Loads images directly from bytes in memory without writing to disk.

        :param image_data_list: The image data list to convert to a PDF file
        :param output_name: The name of the output PDF file
        :param output_path: The directory to save the PDF to (defaults to cwd)
        """
        if not image_data_list:
            return

        images: list[Image.Image] = []

        for image_data in image_data_list:
            # Load image directly from bytes (no disk I/O)
            img = Image.open(BytesIO(image_data))

            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            images.append(img)

        if images:
            save_path = output_path or os.getcwd()
            images[0].save(
                f"{os.path.join(save_path, output_name)}.pdf",
                save_all=True,
                append_images=images[1:],
                quality=self._quality,
                optimize=self._optimize,
            )
