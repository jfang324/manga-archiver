from typing import Optional, Union

from ..types import (
    ProcessedChapter,
    ProcessedDownloadResource,
    ProcessedManga,
)


def _get_nested(data: dict, *keys: str, default: str = "") -> str:
    """
    Safely traverse nested dictionaries.

    :param data: The dictionary to traverse
    :param keys: The sequence of keys to follow
    :param default: Value to return if any key is missing or value is None
    :return: The found value or default
    """
    result: Union[dict, str, None] = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and result:
        return next(iter(result.values()), default)
    return default


def process_manga_data(manga_data: dict) -> list[ProcessedManga]:
    """
    Processes the manga_data dictionary to contain only the following fields:
    {
        title: title of the manga,
        id: mangaID for the API
    }

    :param manga_data: The manga data dictionary
    :return: A list containing the processed manga data
    """

    processed_manga_data: list[ProcessedManga] = []
    data: list[dict] = manga_data["data"]

    for element in data:
        if "id" in element:
            attributes = element.get("attributes", {})
            title = (
                _get_nested(attributes, "title", "en")
                or _get_nested(attributes, "title")
                or "Unknown"
            )
            manga: ProcessedManga = {
                "title": title,
                "id": element["id"],
            }
            processed_manga_data.append(manga)

    return processed_manga_data


def process_chapter_data(chapter_data: dict) -> list[ProcessedChapter]:
    """
    Processes the chapter_data dictionary to contain only the following fields:
    {
        title: title of the chapter,
        id: chapterID for the API,
        chapter: chapter number
    }

    :param chapter_data: The chapter data dictionary
    :return: A list containing the processed chapter data
    """

    processed_chapter_data: list[ProcessedChapter] = []
    data: list[dict] = chapter_data["data"]
    already_contains: set[str] = set()

    for element in data:
        if "id" in element:
            attributes = element.get("attributes", {})
            title: Optional[str] = attributes.get("title")
            chapter: str = (
                attributes.get("chapter")
                if attributes.get("chapter") is not None
                else "0"
            )

            if chapter not in already_contains:
                already_contains.add(chapter)
                processed_chapter_data.append({
                    "title": title,
                    "id": element["id"],
                    "chapter": chapter,
                })

    processed_chapter_data.sort(key=lambda x: float(x["chapter"]))

    return processed_chapter_data


def process_download_resource_data(
    download_resources: dict,
) -> ProcessedDownloadResource:
    """
    Processes the download_resources dictionary into a list of download urls

    :param download_resources: The download resources data dictionary
    :return: A dictionary containing the download urls and hash
    """

    download_urls: list[str] = []
    base_url: str = download_resources["baseUrl"]
    url_hash: str = download_resources["chapter"]["hash"]
    quality: str = "data"

    for element in download_resources["chapter"][quality]:
        download_urls.append(f"{base_url}/{quality}/{url_hash}/{element}")

    return {
        "urls": download_urls,
        "hash": url_hash,
    }
