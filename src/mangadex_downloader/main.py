import asyncio
import curses
import os
import time
from typing import Optional

import aiohttp

from .services.session_manager import SessionManager
from .services.api_access_service import (
    retrieve_chapters,
    retrieve_download_resources,
    retrieve_image_data_list,
    retrieve_mangas,
)
from .services.data_processing_service import (
    process_chapter_data,
    process_download_resource_data,
    process_manga_data,
)
from .services.file_access_service import generate_PDF
from .services.user_interface_service import (
    prompt_list_multi_selection,
    prompt_list_selection,
    prompt_user_input,
)
from .types import ProcessedChapter, ProcessedManga


async def end() -> None:
    await SessionManager.close_session()
    quit()


async def start(stdscr: curses.window) -> None:
    curses.curs_set(0)
    curses.noecho()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)

    session: Optional[aiohttp.ClientSession] = SessionManager.create_session()

    query: str = prompt_user_input(stdscr, "Enter a manga title")

    if query == "":
        await end()

    manga_data: Optional[dict] = await retrieve_mangas(session, query)  # type: ignore[arg-type]
    if manga_data is None:
        await end()
    processed_manga_data: list[ProcessedManga] = process_manga_data(manga_data)  # type: ignore[arg-type]

    selected_manga_index: int = prompt_list_selection(  # type: ignore[assignment]
        stdscr, processed_manga_data, 20, "Select manga"  # type: ignore[arg-type]
    )

    if selected_manga_index is None:
        await end()

    chapter_data: Optional[dict] = await retrieve_chapters(  # type: ignore[arg-type]
        session,  # type: ignore[arg-type]
        processed_manga_data[int(selected_manga_index)]["id"]
    )
    if chapter_data is None:
        await end()
    processed_chapter_data: list[ProcessedChapter] = process_chapter_data(chapter_data)  # type: ignore[arg-type]

    selected_chapters_indexes: list[int] = prompt_list_multi_selection(  # type: ignore[assignment]
        stdscr, processed_chapter_data, 20, "Select chapters"  # type: ignore[arg-type]
    )

    if selected_chapters_indexes is None or len(selected_chapters_indexes) == 0:
        await end()

    selected_chapter_ids: list[str] = [
        processed_chapter_data[i]["id"] for i in selected_chapters_indexes
    ]
    all_download_resources_tasks = [
        retrieve_download_resources(session, id) for id in selected_chapter_ids  # type: ignore[arg-type]
    ]
    all_download_resources = await asyncio.gather(*all_download_resources_tasks)  # type: ignore[assignment]

    link_batches: list[list[str]] = [
        process_download_resource_data(dr)["urls"] for dr in all_download_resources if dr is not None  # type: ignore[misc]
    ]
    all_batch_download_tasks = [
        retrieve_image_data_list(session, link_batch) for link_batch in link_batches  # type: ignore[arg-type]
    ]
    all_image_data_lists = await asyncio.gather(*all_batch_download_tasks)  # type: ignore[assignment]

    stdscr.clear()
    start_time = time.time()

    for i in range(len(all_image_data_lists)):
        if all_image_data_lists[i] is None:
            continue
        stdscr.addstr(
            i,
            0,
            f'Downloading {processed_manga_data[int(selected_manga_index)]["title"]} [{processed_chapter_data[selected_chapters_indexes[i]]["chapter"]}]',
            curses.color_pair(1),
        )
        stdscr.refresh()

        generate_PDF(
            all_image_data_lists[i],  # type: ignore[arg-type]
            f'{processed_manga_data[int(selected_manga_index)]["title"]} [{processed_chapter_data[selected_chapters_indexes[i]]["chapter"]}]',
        )

    elapsed_time = time.time() - start_time

    print(
        "\033[31m"
        + f"Finished downloading {len(all_image_data_lists)} chapters of {processed_manga_data[selected_manga_index]['title']} in {elapsed_time:.2f} seconds"
        + "\033[0m"
    )
    print("\033[31m" + f"Saved to {os.getcwd()}" + "\033[0m")

    await end()


def curses_main(stdscr: curses.window) -> None:
    asyncio.run(start(stdscr))


def main():
    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()
