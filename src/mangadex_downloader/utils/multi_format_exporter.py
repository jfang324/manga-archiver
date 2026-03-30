import re
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..enums import OutputFormat


class MultiFormatExporter:
    """
    Exporter for merging images into a merged format.
    """

    def _sanitize(self, path: str) -> str:
        """
        Sanitize a path to be used as a filename.

        Args:
            path (str): The path to sanitize

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

    # ruff: disable[C901] - This function is complex but we will refactor it after we add epub support
    def generate(
        self,
        image_data_list: list[bytes],
        output_directory: Path,
        output_name: str,
        output_format: OutputFormat,
        quality: int = 75,
        optimize: bool = False,
    ) -> str:
        """
        Merge the image data list into a merged format.
        Loads images directly from bytes in memory without writing to disk.

        Args:
            image_data_list (list[bytes]): The list of image data to merge
            output_directory (Path): The directory to save the file
            output_name (str): The name of the output file
            output_format (OutputFormat): The format of the output file
            quality (int): The quality of the PDF (1-100, default: 75)
            optimize (bool): Whether to optimize PDF file size (default: False)

        Returns:
            str: The path to the generated file

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

        images: list[Image.Image] = []

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
                with zipfile.ZipFile(
                    full_output_path, "w", compression=zipfile.ZIP_DEFLATED
                ) as cbz:
                    for i, img in enumerate(images, start=1):
                        img_buf = BytesIO()
                        img.save(img_buf, format="PNG")  # or "JPEG" for smaller files
                        img_buf.seek(0)
                        cbz.writestr(f"page_{i:03}.png", img_buf.read())
            else:
                images[0].save(
                    full_output_path,
                    save_all=True,
                    append_images=images[1:],
                    quality=quality,
                    optimize=optimize,
                )

            return str(full_output_path)
        finally:
            for img in images:
                img.close()

    # ruff: enable[C901]
