import os
import tempfile
from PIL import Image
import imghdr


def is_image(file_path: str) -> bool:
    """
    Checks if a file is an image

    :param file_path: The path to the file
    :return: True if the file is an image, False otherwise
    """

    return (
        os.path.exists(file_path)
        and os.path.isfile(file_path)
        and imghdr.what(file_path) is not None
    )


def save_image(image_data: bytes, file_path: str) -> None:
    """
    Saves the image data to a file with a name and location determined by the file_path

    :param image_data: The image data to save
    :param file_path: The path to the file to save the image data to
    :return: None
    """

    if image_data:
        with open(file_path, "wb") as file:
            file.write(image_data)


def save_image_list(image_data_list: list[bytes], dir_path: str) -> None:
    """
    Saves each element in image_data_list to a file named after the index of the element

    :param image_data_list: The image data list to save
    :param dir_path: The directory to save the images to
    :return: None
    """

    for i, image_data in enumerate(image_data_list):
        file_path: str = os.path.join(dir_path, f"{i}.jpg")
        save_image(image_data, file_path)


def get_image_list(dir_path: str) -> list[str]:
    """
    Get a list of image files in a directory

    :param dir_path: The path to the directory
    :return: A list of all images in the directory
    """

    try:
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"The directory {dir_path} does not exist")

        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"{dir_path} is not a directory")

        path_list: list[str] = os.listdir(dir_path)
        image_list: list[str] = []

        for path in path_list:
            full_path: str = os.path.join(dir_path, path)

            if is_image(full_path):
                image_list.append(full_path)

        return image_list
    except Exception as e:
        print(e)
        return []


def convert_images_to_pdf(
    image_list: list[str], output_path: str, output_name: str
) -> None:
    """
    Converts a list of images to a PDF file

    :param image_list: A list of image files to be converted
    :param output_path: The path to the output directory
    :param output_name: The name of the output PDF file
    """

    images: list[Image.Image] = []

    for image in image_list:
        if is_image(image):
            img: Image.Image = Image.open(image)

            if img.mode == "P":
                img = img.convert("RGB")

            images.append(img)

    if len(images) > 1:
        images[0].save(
            f"{os.path.join(output_path, output_name)}.pdf",
            save_all=True,
            append_images=images[1:],
            optimize=True,
        )


def generate_PDF(image_data_list: list[bytes], output_name: str) -> None:
    """
    Generates a PDF file from the image data list by creating a temporary directory and saving each image to a file
    in the temporary directory, then converting the temporary directory to a PDF file

    :param image_data_list: The image data list to convert to a PDF file
    :param output_name: The name of the output PDF file
    :return: None
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        save_image_list(image_data_list, temp_dir)
        image_list: list[str] = get_image_list(temp_dir)
        image_list.sort(key=lambda x: int(x.split(os.path.sep)[-1].split(".")[0]))

        convert_images_to_pdf(image_list, os.getcwd(), output_name)
