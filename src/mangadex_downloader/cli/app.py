"""Main CLI application logic."""

import asyncio
import curses
import os
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from ..integrations import MangaDexApiClient
from ..types import ProcessedChapter, ProcessedManga
from ..utils import DownloadClient, PdfGenerator, SessionManager
from .curses_ui import (
    prompt_list_multi_selection,
    prompt_list_selection,
    prompt_user_input,
)


@dataclass
class Config:
    """Configuration for the CLI application."""

    page_size: int = 10
    quality: int = 75
    optimize: bool = False
    data_saver: bool = False


async def end() -> None:
    """End the application and close the session."""
    await SessionManager.close_session()
    quit()


async def start(stdscr: curses.window, config: Config) -> None:
    """Main application flow.

    :param stdscr: The curses window object
    :param config: Application configuration
    """
    # Initialize curses settings
    curses.curs_set(0)
    curses.noecho()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)

    session: Optional[aiohttp.ClientSession] = SessionManager.create_session()

    # Get user query
    query: str = prompt_user_input(stdscr, "Enter a manga title")
    if query == "":
        await end()

    # Create API client with data-saver setting
    mangadex = MangaDexApiClient(session, data_saver=config.data_saver)

    # Search for manga
    mangas: list[ProcessedManga] = await mangadex.search_manga(query)
    if not mangas:
        await end()

    # Select manga (using page_size from config)
    selected_manga_index: Optional[int] = prompt_list_selection(
        stdscr,
        mangas,
        config.page_size,
        "Select manga",  # type: ignore[arg-type]
    )
    if selected_manga_index is None:
        await end()

    assert selected_manga_index is not None
    selected_manga: ProcessedManga = mangas[selected_manga_index]

    # Get chapters
    chapters: list[ProcessedChapter] = await mangadex.get_chapters(
        selected_manga["id"]
    )
    if not chapters:
        await end()

    # Select chapters (using page_size from config)
    selected_chapters_indexes: Optional[list[int]] = (
        prompt_list_multi_selection(
            stdscr, chapters, config.page_size, "Select chapters"  # type: ignore[arg-type]
        )
    )
    if not selected_chapters_indexes:
        await end()

    assert selected_chapters_indexes is not None
    # Get download resources for each selected chapter
    resource_tasks = [
        mangadex.get_download_resource(chapters[i]["id"])
        for i in selected_chapters_indexes
    ]
    download_resources = await asyncio.gather(*resource_tasks)

    # Create download client
    downloader = DownloadClient(session)

    # Download ALL images from ALL chapters in parallel
    stdscr.clear()
    start_time = time.time()

    # Show download starting message
    stdscr.addstr(
        0,
        0,
        f"Downloading {len(selected_chapters_indexes)} chapters of {selected_manga['title']}...",
        curses.color_pair(1),
    )
    stdscr.refresh()

    # Create download tasks for all chapters
    download_tasks = [
        downloader.download_images(resource["urls"])
        for resource in download_resources
    ]
    all_chapter_images = await asyncio.gather(*download_tasks)

    # Generate PDFs for each chapter after all downloads complete
    pdf_generator = PdfGenerator(
        quality=config.quality, optimize=config.optimize
    )
    for i, images in enumerate(all_chapter_images):
        chapter_title = chapters[selected_chapters_indexes[i]]["chapter"]
        pdf_name = f"{selected_manga['title']} [{chapter_title}]"
        pdf_generator.generate(images, pdf_name)

    elapsed_time = time.time() - start_time

    print(
        "\033[31m"
        + f"Finished downloading {len(download_resources)} chapters of "
        f"{selected_manga['title']} in {elapsed_time:.2f} seconds"
        + "\033[0m"
    )
    print("\033[31m" + f"Saved to {os.getcwd()}" + "\033[0m")

    await end()


def _curses_main(stdscr: curses.window, config: Config) -> None:
    """Wrapper to run async start in curses context.

    :param stdscr: The curses window object
    :param config: Application configuration
    """
    asyncio.run(start(stdscr, config))


def run_app(config: Config) -> None:
    """Run the CLI application.

    :param config: Application configuration
    """

    def wrapper(stdscr: curses.window) -> None:
        _curses_main(stdscr, config)

    curses.wrapper(wrapper)
