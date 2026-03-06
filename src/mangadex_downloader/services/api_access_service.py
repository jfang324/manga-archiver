import asyncio

from typing import Optional

import aiohttp

from ..constants import (
    MANGADEX_ROOT_URL,
    MANGADEX_RESOURCE_LINKS_URL,
)


async def fetch(session: aiohttp.ClientSession, url: str, params: dict = {}) -> dict:
    """
    Makes a GET request to the url and returns the response

    :param session: The aiohttp.ClientSession to use
    :param url: The url to fetch
    :param params: The query parameters to pass to the url
    :return: The dictionary resulting from calling .json() on the response
    """

    async with session.get(url, params=params) as response:
        if response and response.status == 200:
            return await response.json()
        else:
            raise Exception(
                f"Error fetching url: {url}. Status code: {response.status}"
            )


async def retrieve_mangas(session: aiohttp.ClientSession, query: str) -> Optional[dict]:
    """
    Retrieves manga's similar to the query from the MangaDex API

    :param session: The aiohttp.ClientSession to use
    :param query: The query to search for
    :return: A dictionary containing information for similar mangas
    """

    try:
        url: str = f"{MANGADEX_ROOT_URL}?title={query}"
        params: dict = {"limit": 100}

        return await fetch(session, url, params)
    except Exception as e:
        print(e)
        return None


async def retrieve_chapters(session: aiohttp.ClientSession, manga_id: str) -> Optional[dict]:
    """
    Retrieves chapters of the manga with the given manga_id from the MangaDex API

    :param session: The aiohttp.ClientSession to use
    :param manga_id: The id of the manga to retrieve chapters for
    :return: A dictionary containing information for chapters of the manga
    """

    try:
        url: str = f"{MANGADEX_ROOT_URL}/{manga_id}/feed"
        params: dict = {
            "translatedLanguage[]": ["en"],
            "limit": 500,
            "includeEmptyPages": 0,
        }

        return await fetch(session, url, params)
    except Exception as e:
        print(e)
        return None


async def retrieve_download_resources(
    session: aiohttp.ClientSession, chapter_id: str
) -> Optional[dict]:
    """
    Retrieves download resources of the chapter with the given chapter_id from the MangaDex API

    :param session: The aiohttp.ClientSession to use
    :param chapter_id: The id of the chapter to retrieve download resources for
    :return: A dictionary containing information for download resources of the chapter
    """

    try:
        url: str = f"{MANGADEX_RESOURCE_LINKS_URL}/{chapter_id}"

        return await fetch(session, url)
    except Exception as e:
        print(e)
        return None


async def retrieve_image_data(session: aiohttp.ClientSession, image_url: str) -> bytes:
    """
    Retrieves the image data from the given image url

    :param session: The aiohttp.ClientSession to use
    :param image_url: The url of the image to retrieve data for
    :return: The binary data of the image
    """

    async with session.get(image_url) as response:
        if response and response.status == 200:
            return await response.read()
        else:
            raise Exception(
                f"Failed to retrieve image data for {image_url}. Status code: {response.status}"
            )


async def retrieve_image_data_list(
    session: aiohttp.ClientSession, url_list: list[str]
) -> Optional[list[bytes]]:
    """
    Retrieves the image data from the given image urls

    :param session: The aiohttp.ClientSession to use
    :param url_list: The urls of the images to retrieve data for
    :return: A list containing the binary data of the images
    """

    try:
        tasks = [retrieve_image_data(session, url) for url in url_list]

        return await asyncio.gather(*tasks)
    except Exception as e:
        print(e)
        return None
