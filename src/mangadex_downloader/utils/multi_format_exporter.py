import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image

from ..enums import OutputFormat

logger = logging.getLogger(__name__)


class MultiFormatExporter:
    """Exporter for merging images into a merged format."""

    def _sanitize(self, path: str) -> str:
        """Sanitize a path to be used as a filename.

        Args:
            path: The path to sanitize

        Returns:
            str: The sanitized path
        """
        # Remove characters that are invalid on Windows or Unix filesystems
        # This includes: < > : " / \ | ? * and control characters
        # All other characters (alphanumeric, spaces, hyphens, underscores, periods, brackets, parentheses) are kept
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", path)

        # Replace multiple spaces with single space
        sanitized = re.sub(r"\s+", " ", sanitized)

        # Strip leading/trailing whitespace
        sanitized = sanitized.strip()

        # Ensure filename isn't empty
        if not sanitized:
            sanitized = "untitled"

        return sanitized

    def _generate_cbz(
        self, images: list[Image.Image], write_location: Path | BytesIO
    ) -> bytes:
        """Generate a CBZ file from a list of images.

        Args:
            images: The list of images to generate
            write_location: The location to write the CBZ file

        Returns:
            bytes: The CBZ file data
        """
        try:
            with zipfile.ZipFile(
                write_location, "w", compression=zipfile.ZIP_DEFLATED
            ) as cbz:
                for i, img in enumerate(images, start=1):
                    img_buf = BytesIO()
                    img.save(img_buf, format="PNG")
                    img_buf.seek(0)
                    cbz.writestr(f"page_{i:03}.png", img_buf.read())

            return cast("BytesIO", write_location).getvalue()
        except Exception as e:
            logger.error("Error generating CBZ file: %s", e)
            raise

    def _generate_pdf(
        self,
        images: list[Image.Image],
        write_location: Path | BytesIO,
        quality: int = 75,
        optimize: bool = False,
    ) -> bytes:
        """Generate a PDF file from a list of images.

        Args:
            images: The list of images to generate
            write_location: The location to write the PDF file

        Returns:
            bytes: The PDF file data
        """
        try:
            images[0].save(
                write_location,
                format=str(OutputFormat.PDF),
                save_all=True,
                append_images=images[1:],
                quality=quality,
                optimize=optimize,
            )

            return cast("BytesIO", write_location).getvalue()
        except Exception as e:
            logger.error("Error generating PDF file: %s", e)
            raise

    # ruff: disable[C901] - The complexity of this function largely comes from input validation which must be done
    def generate(
        self,
        image_data_list: list[bytes],
        output_directory: Path,
        output_name: str,
        output_format: OutputFormat,
        quality: int = 75,
        optimize: bool = False,
        return_bytes: bool = False,
    ) -> tuple[str, bytes]:
        """Merge the image data list into a merged format.

        Loads images directly from bytes in memory without writing to disk.

        Args:
            image_data_list: The list of image data to merge
            output_directory: The directory to save the file
            output_name: The name of the output file
            output_format: The format of the output file
            quality: The quality of the PDF (1-100, default: 75)
            optimize: Whether to optimize PDF file size (default: False)
            return_bytes: If True, return file bytes instead of writing to disk (default: False)

        Returns:
            tuple[str, bytes]: (full_name, file_bytes)
                - full_name: The full filename with extension
                - file_bytes: If return_bytes=True, the file bytes; otherwise empty bytes

        Raises:
            ValueError: If any of the arguments are invalid
        """
        if not image_data_list:
            raise ValueError("Image data list cannot be empty")

        if not output_directory.exists() and not output_directory.is_dir():
            raise ValueError(
                f"Output directory must be a valid directory: {output_directory}"
            )

        if not output_name:
            raise ValueError("Output name cannot be empty")

        if quality < 1 or quality > 100:
            raise ValueError("Quality must be between 1 and 100")

        full_output_path: Path = (
            output_directory / f"{self._sanitize(output_name)}.{str(output_format)}"
        )
        full_name: str = f"{self._sanitize(output_name)}.{str(output_format)}"

        images: list[Image.Image] = []

        output_data: bytes = b""

        try:
            for image_data in image_data_list:
                try:
                    img = Image.open(BytesIO(image_data))
                except Exception as e:
                    raise ValueError(f"Invalid image data: {e}") from e

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                images.append(img)

            if not images:
                raise ValueError("No valid images to generate output")

            if output_format == OutputFormat.CBZ:
                write_location = BytesIO() if return_bytes else full_output_path
                file_data = self._generate_cbz(images, write_location)
            else:
                write_location = BytesIO() if return_bytes else full_output_path
                file_data = self._generate_pdf(
                    images, write_location, quality, optimize
                )

            if return_bytes:
                output_data = file_data

            return full_name, output_data
        finally:
            for img in images:
                img.close()

    # ruff: enable[C901]
