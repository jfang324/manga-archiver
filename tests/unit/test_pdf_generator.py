"""Unit tests for PdfGenerator."""

import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.mangadex_downloader.utils.pdf_generator import PdfGenerator


class TestPdfGeneratorInit:
    """Test PdfGenerator initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        generator = PdfGenerator()
        assert generator._quality == 75
        assert generator._optimize is False

    def test_init_with_custom_values(self):
        """Test initialization with custom parameters."""
        generator = PdfGenerator(quality=90, optimize=True)
        assert generator._quality == 90
        assert generator._optimize is True


class TestPdfGeneratorGenerate:
    """Test generate method."""

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    @patch("os.path.join")
    def test_generate_with_valid_images(self, mock_join, mock_getcwd, mock_image_open):
        """Test PDF generation with valid images."""
        # Setup mocks
        mock_getcwd.return_value = "/tmp"
        mock_join.return_value = "/tmp/test.pdf"
        
        # Create a mock image that behaves like a PIL Image
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img
        
        # Create image data (simple valid PNG bytes)
        img_data = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()
        
        generator = PdfGenerator()
        generator.generate([img_bytes, img_bytes], "test")
        
        # Verify Image.open was called for each image
        assert mock_image_open.call_count == 2

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    def test_generate_empty_list(self, mock_getcwd, mock_image_open):
        """Test PDF generation with empty image list."""
        generator = PdfGenerator()
        generator.generate([], "test")
        
        # Should return early without calling Image.open
        mock_image_open.assert_not_called()

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    @patch("os.path.join")
    def test_generate_converts_rgba_to_rgb(self, mock_join, mock_getcwd, mock_image_open):
        """Test RGBA images are converted to RGB."""
        mock_getcwd.return_value = "/tmp"
        mock_join.return_value = "/tmp/test.pdf"
        
        mock_img = MagicMock()
        mock_img.mode = "RGBA"
        mock_img.convert = MagicMock(return_value=mock_img)
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img
        
        # Create RGBA image data
        img_data = BytesIO()
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(img_data, format="PNG")
        img_bytes = img_data.getvalue()
        
        generator = PdfGenerator()
        generator.generate([img_bytes], "test")
        
        # Verify convert was called
        mock_img.convert.assert_called_once_with("RGB")

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    @patch("os.path.join")
    def test_generate_converts_palette_to_rgb(self, mock_join, mock_getcwd, mock_image_open):
        """Test P (palette) mode images are converted to RGB."""
        mock_getcwd.return_value = "/tmp"
        mock_join.return_value = "/tmp/test.pdf"
        
        mock_img = MagicMock()
        mock_img.mode = "P"
        mock_img.convert = MagicMock(return_value=mock_img)
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img
        
        generator = PdfGenerator()
        generator.generate([b"test_data"], "test")
        
        # Verify convert was called
        mock_img.convert.assert_called_once_with("RGB")

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    @patch("os.path.join")
    def test_generate_uses_custom_output_path(self, mock_join, mock_getcwd, mock_image_open):
        """Test PDF generation with custom output path."""
        mock_join.return_value = "/custom/path/test.pdf"
        
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img
        
        generator = PdfGenerator()
        generator.generate([b"test_data"], "test", output_path="/custom/path")
        
        # Verify path.join was called with custom path
        mock_join.assert_called_once()
        assert "/custom/path" in str(mock_join.call_args)

    @patch("PIL.Image.open")
    @patch("os.getcwd")
    @patch("os.path.join")
    def test_generate_uses_quality_and_optimize_settings(self, mock_join, mock_getcwd, mock_image_open):
        """Test that quality and optimize settings are passed to save."""
        mock_getcwd.return_value = "/tmp"
        mock_join.return_value = "/tmp/test.pdf"
        
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.save = MagicMock()
        mock_image_open.return_value = mock_img
        
        generator = PdfGenerator(quality=90, optimize=True)
        generator.generate([b"test_data", b"test_data"], "test")
        
        # Verify save was called with correct parameters
        call_args = mock_img.save.call_args
        assert call_args[1]["quality"] == 90
        assert call_args[1]["optimize"] is True
