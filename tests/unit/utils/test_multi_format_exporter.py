from io import BytesIO

import pytest
from PIL import Image

from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.utils.multi_format_exporter import MultiFormatExporter


class TestSanitize:
    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("Manga Title", "Manga Title"),
            ("Test<>:|?*File", "TestFile"),
            ("Test   Multiple   Spaces", "Test Multiple Spaces"),
            ("  Test  ", "Test"),
            ("", "untitled"),
        ],
        ids=[
            "normal_name",
            "remove_invalid_chars",
            "collapse_multiple_spaces",
            "strip_whitespace",
            "empty_returns_untitled",
        ],
    )
    def test_sanitize_various_inputs(self, input_str: str, expected: str) -> None:
        exporter = MultiFormatExporter()
        result = exporter._sanitize(input_str)

        assert result == expected


class TestValidateInputs:
    @pytest.mark.parametrize(
        ("image_data_list", "output_name", "quality", "expected_error"),
        [
            ([], "test", 75, "Image data list cannot be empty"),
            ([b"data"], "", 75, "Output name cannot be empty"),
            ([b"data"], "test", 0, "Quality must be between 1 and 100"),
            ([b"data"], "test", 101, "Quality must be between 1 and 100"),
        ],
        ids=[
            "empty_image_list",
            "empty_output_name",
            "quality_below_min",
            "quality_above_max",
        ],
    )
    def test_validate_inputs_raises_errors(
        self, image_data_list, output_name, quality, expected_error, tmp_path
    ) -> None:
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match=expected_error):
            exporter._validate_inputs(image_data_list, tmp_path, output_name, quality)

    def test_validate_inputs_invalid_directory_path(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(ValueError, match="Output directory must be a valid directory"):
            exporter._validate_inputs([b"data"], file_path, "test", 75)

    def test_validate_inputs_nonexistent_directory(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="Output directory must be a valid directory"):
            exporter._validate_inputs([b"data"], nonexistent, "test", 75)

    def test_validate_inputs_valid_inputs(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        exporter._validate_inputs([b"data"], tmp_path, "test", 75)


class TestLoadImages:
    @pytest.mark.parametrize(
        ("image_bytes",),
        [(b"invalid",), (b"",)],
        ids=["corrupted_bytes", "empty_bytes"],
    )
    def test_load_images_invalid_data_raises(self, image_bytes) -> None:
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="Invalid image data"):
            exporter._load_images([image_bytes])

    def test_load_images_empty_list_raises(self) -> None:
        exporter = MultiFormatExporter()

        with pytest.raises(ValueError, match="No valid images to generate output"):
            exporter._load_images([])

    @pytest.mark.parametrize(
        ("mode",),
        [("RGB",), ("RGBA",), ("P",)],
        ids=["rgb", "rgba", "palette"],
    )
    def test_load_images_converts_modes(self, mode) -> None:
        exporter = MultiFormatExporter()

        img = Image.new(mode, (100, 100))
        buf = BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        images = exporter._load_images([image_bytes])

        assert images[0].mode == "RGB"

    def test_load_images_single_valid_image(self) -> None:
        exporter = MultiFormatExporter()

        img = Image.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        images = exporter._load_images([image_bytes])

        assert images[0].mode == "RGB"

    def test_load_images_multiple_valid_images(self) -> None:
        exporter = MultiFormatExporter()

        image_bytes_list = []
        for color in ["red", "green", "blue"]:
            img = Image.new("RGB", (100, 100), color=color)
            buf = BytesIO()
            img.save(buf, format="PNG")
            image_bytes_list.append(buf.getvalue())

        images = exporter._load_images(image_bytes_list)

        assert all(img.mode == "RGB" for img in images)


class TestGeneratePdf:
    def test_generate_pdf_to_path(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        images = [Image.new("RGB", (100, 100), color="red")]

        output_file = tmp_path / "test.pdf"
        exporter._generate_pdf(images, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_generate_pdf_to_buffer(self) -> None:
        exporter = MultiFormatExporter()
        images = [Image.new("RGB", (100, 100), color="red")]

        buffer = BytesIO()
        exporter._generate_pdf(images, buffer)

        assert buffer.tell() > 0

    def test_generate_pdf_empty_images_raises(self) -> None:
        exporter = MultiFormatExporter()

        with pytest.raises(IndexError):
            exporter._generate_pdf([], BytesIO())

    def test_generate_pdf_with_quality_and_optimize(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        images = [Image.new("RGB", (100, 100), color="red")]

        output_file = tmp_path / "test.pdf"
        exporter._generate_pdf(images, output_file, quality=75, optimize=False)

        assert output_file.exists()
        assert output_file.stat().st_size > 0


class TestGenerateCbz:
    def test_generate_cbz_to_path(self, tmp_path) -> None:
        exporter = MultiFormatExporter()
        images = [Image.new("RGB", (100, 100), color="red")]

        output_file = tmp_path / "test.cbz"
        exporter._generate_cbz(images, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_generate_cbz_to_buffer(self) -> None:
        exporter = MultiFormatExporter()
        images = [Image.new("RGB", (100, 100), color="red")]

        buffer = BytesIO()
        exporter._generate_cbz(images, buffer)

        assert buffer.getvalue()[:2] == b"PK"


class TestMultiFormatExporterGenerate:
    @pytest.fixture
    def _image_bytes(self) -> bytes:
        img = Image.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_generate_pdf_to_path(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate([_image_bytes], tmp_path, "test", OutputFormat.PDF)

        assert full_name == "test.pdf"
        assert (tmp_path / "test.pdf").exists()
        assert file_data == b""

    def test_generate_pdf_to_buffer(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate(
            [_image_bytes], tmp_path, "test", OutputFormat.PDF, return_bytes=True
        )

        assert full_name == "test.pdf"
        assert len(file_data) > 0

    def test_generate_cbz_to_path(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate([_image_bytes], tmp_path, "test", OutputFormat.CBZ)

        assert full_name == "test.cbz"
        assert (tmp_path / "test.cbz").exists()
        assert file_data == b""

    def test_generate_cbz_to_buffer(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate(
            [_image_bytes], tmp_path, "test", OutputFormat.CBZ, return_bytes=True
        )

        assert full_name == "test.cbz"
        assert len(file_data) > 0

    def test_generate_epub_to_path(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate(
            [_image_bytes], tmp_path, "test", OutputFormat.EPUB
        )

        assert full_name == "test.epub"
        assert (tmp_path / "test.epub").exists()
        assert file_data == b""

    def test_generate_epub_to_buffer(self, tmp_path, _image_bytes) -> None:
        exporter = MultiFormatExporter()
        full_name, file_data = exporter.generate(
            [_image_bytes], tmp_path, "test", OutputFormat.EPUB, return_bytes=True
        )

        assert full_name == "test.epub"
        assert len(file_data) > 0
