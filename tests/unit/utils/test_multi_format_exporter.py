import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.mangadex_downloader.enums import OutputFormat
from src.mangadex_downloader.utils.multi_format_exporter import MultiFormatExporter


## TODO: add stronger tests after adding support for more formats and refactoring
# current test is weak and doesn't actually test the merging step
class TestMultiFormatExporterGenerate:
    @patch("PIL.Image.open")
    def test_generate_with_valid_images(self, mock_image_open):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        img_data = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()

        exporter = MultiFormatExporter()
        exporter.generate(
            [img_bytes, img_bytes],
            temp_dir,
            "test",
            OutputFormat.PDF,
        )

        assert mock_image_open.call_count == 2

    def test_generate_empty_list_raises_error(self):
        temp_dir = Path(tempfile.gettempdir())
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="cannot be empty"):
            exporter.generate([], temp_dir, "test", OutputFormat.PDF)

    def test_generate_invalid_output_directory_raises_error(self):
        temp_dir = Path(tempfile.gettempdir())
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="valid directory"):
            exporter.generate(
                [b"test_data"], temp_dir / "invalid", "test", OutputFormat.PDF
            )

    def test_generate_invalid_output_name_raises_error(self):
        temp_dir = Path(tempfile.gettempdir())
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="cannot be empty"):
            exporter.generate([b"test_data"], temp_dir, "", OutputFormat.PDF)

    def test_generate_invalid_quality_raises_error(self):
        temp_dir = Path(tempfile.gettempdir())
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="between 1 and 100"):
            exporter.generate(
                [b"test_data"], temp_dir, "test", OutputFormat.PDF, quality=0
            )

    @patch("PIL.Image.open")
    def test_generate_converts_rgba_to_rgb(self, mock_image_open):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGBA"
        mock_img.convert = MagicMock(return_value=mock_img)
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        img_data = BytesIO()
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()

        exporter = MultiFormatExporter()
        exporter.generate([img_bytes], temp_dir, "test", OutputFormat.PDF)

        mock_img.convert.assert_called_once_with("RGB")

    @patch("PIL.Image.open")
    def test_generate_converts_palette_to_rgb(self, mock_image_open):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "P"
        mock_img.convert = MagicMock(return_value=mock_img)
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        exporter = MultiFormatExporter()
        exporter.generate([b"test_data"], temp_dir, "test", OutputFormat.PDF)

        mock_img.convert.assert_called_once_with("RGB")

    @patch("PIL.Image.open")
    def test_generate_uses_custom_output_directory(self, mock_image_open):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        exporter = MultiFormatExporter()
        result = exporter.generate([b"test_data"], temp_dir, "test", OutputFormat.PDF)

        full_name, file_data = result
        assert full_name.startswith("test")
        assert file_data == []

    # TODO: add tests for other formats
    @patch("PIL.Image.open")
    def test_generate_uses_quality_and_optimize_settings(self, mock_image_open):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        exporter = MultiFormatExporter()
        exporter.generate(
            [b"test_data", b"test_data"],
            temp_dir,
            "test",
            OutputFormat.PDF,
            quality=90,
            optimize=True,
        )

        call_args = mock_img.save.call_args
        assert call_args[1]["quality"] == 90
        assert call_args[1]["optimize"] is True

    @patch("src.mangadex_downloader.utils.multi_format_exporter.zipfile.ZipFile")
    @patch("PIL.Image.open")
    def test_generate_pdf_uses_pillow_save(self, mock_image_open, mock_zipfile):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        img_data = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()

        exporter = MultiFormatExporter()
        exporter.generate([img_bytes], temp_dir, "test", OutputFormat.PDF)

        # Verify Pillow save was called (for PDF)
        mock_img.save.assert_called_once()
        # Verify ZipFile was NOT called (not CBZ)
        mock_zipfile.assert_not_called()

    @patch("src.mangadex_downloader.utils.multi_format_exporter.zipfile.ZipFile")
    @patch("PIL.Image.open")
    def test_generate_cbz_uses_zipfile(self, mock_image_open, mock_zipfile):
        temp_dir = Path(tempfile.gettempdir())

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img

        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__ = MagicMock(return_value=mock_zip)
        mock_zipfile.return_value.__exit__ = MagicMock(return_value=None)

        img_data = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()

        exporter = MultiFormatExporter()
        exporter.generate([img_bytes], temp_dir, "test", OutputFormat.CBZ)

        # Verify ZipFile was called (for CBZ)
        mock_zipfile.assert_called_once()
        # Verify writestr was called to add images to zip
        mock_zip.writestr.assert_called()
        # Verify Pillow save was NOT called with save_all=True (not PDF format)
        # CBZ saves to BytesIO buffer, not directly to file
        for call in mock_img.save.call_args_list:
            assert call[1].get("save_all") is not True
