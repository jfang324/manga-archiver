import os
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from src.mangadex_downloader.services.file_access_service import *
from tests.mock_data import *


class TestIsImage:
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("imghdr.what", return_value="JPEG")
    def test_is_image_with_valid_file_returns_true(
        self, mock_exists: MagicMock, mock_isfile: MagicMock, mock_what: MagicMock
    ):
        assert is_image(mock_image_paths[0])

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=False)
    def test_is_image_with_invalid_file_returns_false(
        self, mock_exists: MagicMock, mock_isfile: MagicMock
    ):
        assert not is_image(mock_image_paths[0])


class TestSaveImage:
    def create_mock_file() -> MagicMock:
        mock_file: MagicMock = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.write.return_value = None

        return mock_file

    @patch("builtins.open", new_callable=create_mock_file)
    def test_save_image_writes_bytes_to_file(self, mock_open: MagicMock):
        image_data: bytes = mock_image_data_list[0]
        file_path: str = mock_image_paths[0]

        save_image(image_data, file_path)
        mock_open.assert_called_once_with(file_path, "wb")
        mock_open().__enter__().write.assert_called_once_with(image_data)

    @patch("builtins.open", new_callable=create_mock_file)
    def test_save_image_does_not_write_bytes_to_file_if_image_data_is_none(
        self, mock_open: MagicMock
    ):
        image_data: bytes = None
        file_path: str = mock_image_paths[0]

        save_image(image_data, file_path)
        mock_open.assert_not_called()


class TestSaveImageList:
    @patch("src.mangadex_downloader.services.file_access_service.save_image")
    def test_save_image_list_saves_each_image_in_image_data_list_to_a_file(
        self, mock_save_image: MagicMock
    ):
        image_data_list: list[bytes] = mock_image_data_list
        directory: str = mock_directory

        save_image_list(image_data_list, directory)
        for i, image_data in enumerate(image_data_list):
            assert mock_save_image.call_args_list[i][0][0] == image_data
            assert mock_save_image.call_args_list[i][0][1] == os.path.join(
                directory, f"{i}.jpg"
            )

        assert mock_save_image.call_count == len(image_data_list)


class TestGetImageList:
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=mock_image_paths)
    @patch(
        "src.mangadex_downloader.services.file_access_service.is_image",
        return_value=True,
    )
    def test_get_image_list_with_valid_directory_returns_correct_list(
        self,
        mock_exists: MagicMock,
        mock_isdir: MagicMock,
        mock_listdir: MagicMock,
        mock_is_image: MagicMock,
    ):
        assert get_image_list(mock_directory) == [
            os.path.join(mock_directory, file) for file in mock_image_paths
        ]

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=mock_image_paths)
    @patch(
        "src.mangadex_downloader.services.file_access_service.is_image",
        return_value=False,
    )
    def test_get_image_list_with_valid_directory_with_no_images_returns_empty_list(
        self,
        mock_exists: MagicMock,
        mock_isdir: MagicMock,
        mock_listdir: MagicMock,
        mock_is_image: MagicMock,
    ):
        assert get_image_list(mock_directory) == []

    @patch("os.path.exists", return_value=False)
    def test_get_image_list_with_non_existing_directory_returns_empty_list(
        self, mock_exists: MagicMock
    ):
        assert get_image_list("/non/existing/directory") == []

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=False)
    def test_get_image_list_with_non_directory_returns_empty_list(
        self, mock_exists: MagicMock, mock_isdir: MagicMock
    ):
        assert get_image_list("/path/to/file.txt") == []


class TestConvertImagesToPdf:
    def create_mock_directory() -> MagicMock:
        mock_directory: MagicMock = MagicMock()
        mock_directory.__enter__.return_value = "/path/to/temp/dir"
        mock_directory.__exit__ = None

    @patch("tempfile.TemporaryDirectory", new_callable=create_mock_directory)
    @patch(
        "src.mangadex_downloader.services.file_access_service.is_image",
        return_value=True,
    )
    @patch("PIL.Image.open", return_value=Image.new("RGB", (100, 100)))
    @patch("PIL.Image.Image.save", return_value=None)
    @patch("os.path.join", return_value="/path/to/output.pdf")
    def test_convert_images_to_pdf_with_valid_file_list_and_output_path_and_name(
        self,
        mock_join: MagicMock,
        mock_save: MagicMock,
        mock_open: MagicMock,
        mock_is_image: MagicMock,
        mock_tempdir: MagicMock,
    ):
        output_path: str = "/path/to/output"
        output_name: str = "output"
        convert_images_to_pdf(mock_image_paths, output_path, output_name)

        for file in mock_image_paths:
            mock_open.assert_any_call(file)

        mock_save.assert_called_once_with(
            f"{os.path.join(output_path, output_name)}.pdf",
            save_all=True,
            append_images=[
                Image.new("RGB", (100, 100)) for i in range(len(mock_image_paths))
            ][1:],
            optimize=True,
        )

    @patch("tempfile.TemporaryDirectory", new_callable=create_mock_directory)
    @patch("src.mangadex_downloader.services.file_access_service.is_image")
    @patch("PIL.Image.open", return_value=Image.new("RGB", (100, 100)))
    @patch("PIL.Image.Image.save", return_value=None)
    @patch("os.path.join", return_value="/path/to/output.pdf")
    def test_convert_images_to_pdf_with_invalid_file_list_skips_invalid_files(
        self,
        mock_join: MagicMock,
        mock_save: MagicMock,
        mock_open: MagicMock,
        mock_is_image: MagicMock,
        mock_tempdir: MagicMock,
    ):
        output_path: str = "/path/to/output"
        output_name: str = "output"
        is_image_list = [False]
        is_image_list.extend([True] * len(mock_image_paths))
        mock_is_image.side_effect = is_image_list
        convert_images_to_pdf(mock_image_paths, output_path, output_name)

        assert mock_open.call_count == len(mock_image_paths) - 1
        assert mock_save.called_once_with(
            f"{os.path.join(output_path, output_name)}.pdf",
            save_all=True,
            append_images=[
                Image.new("RGB", (100, 100)) for i in range(len(mock_image_paths) - 1)
            ][1:],
            optimize=True,
        )

    @patch("PIL.Image.open", return_value=Image.new("RGB", (100, 100)))
    @patch("PIL.Image.Image.save", return_value=None)
    def test_convert_images_to_pdf_with_no_images(
        self, mock_open: MagicMock, mock_save: MagicMock
    ):
        output_path: str = "/path/to/output"
        output_name: str = "output"
        convert_images_to_pdf([], output_path, output_name)

        assert mock_open.call_count == 0
        assert mock_save.call_count == 0
