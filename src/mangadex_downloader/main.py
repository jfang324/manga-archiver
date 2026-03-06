import asyncio
import curses
import os
import time
from .services.session_manager import *
from .services.api_access_service import *
from .services.data_processing_service import *
from .services.user_interface_service import *
from .services.file_access_service import *
from .types import ProcessedChapter, ProcessedManga


async def end() -> None:
    await SessionManager.close_session()
    quit()


async def start(stdscr: curses.window) -> None:
    # Main body of the program

    # Initialize curses settings for UI
    curses.curs_set(0)
    curses.noecho()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)

    # Create a new session
    session: aiohttp.ClientSession = SessionManager.create_session()

    # Prompt user for a initial query
    query: str = prompt_user_input(stdscr, "Enter a manga title")

    if query == "":
        await end()

    # Retrieve and process the API response into a list of mangas similar to the query
    manga_data: dict = await retrieve_mangas(session, query)
    processed_manga_data: list[ProcessedManga] = process_manga_data(manga_data)

    # Prompt user to select a manga out of the list of mangas
    selected_manga_index: int = prompt_list_selection(
        stdscr, processed_manga_data, 20, "Select manga"
    )

    if selected_manga_index == None:
        await end()

    # Retrieve and process the API response into a list of chapters of the selected manga
    chapter_data: dict = await retrieve_chapters(
        session, processed_manga_data[int(selected_manga_index)]["id"]
    )
    processed_chapter_data: list[ProcessedChapter] = process_chapter_data(chapter_data)

    # Prompt user to select a list of chapters to download
    selected_chapters_indexes: list[int] = prompt_list_multi_selection(
        stdscr, processed_chapter_data, 20, "Select chapters"
    )

    if selected_chapters_indexes == None or len(selected_chapters_indexes) == 0:
        await end()

    # Retrieve download resources for the selected chapters
    selected_chapter_ids: list[str] = [
        processed_chapter_data[i]["id"] for i in selected_chapters_indexes
    ]
    all_download_resources_tasks: list[dict] = [
        retrieve_download_resources(session, id) for id in selected_chapter_ids
    ]
    all_download_resources: list[dict] = await asyncio.gather(
        *all_download_resources_tasks
    )

    # Process the download resources into lists of download links and retrieve the image data for each batch
    link_batches: list[list[str]] = [
        process_download_resource_data(dr)["urls"] for dr in all_download_resources
    ]
    all_batch_download_tasks: list[list[bytes]] = [
        retrieve_image_data_list(session, link_batch) for link_batch in link_batches
    ]
    all_image_data_lists: list[list[bytes]] = await asyncio.gather(
        *all_batch_download_tasks
    )

    # Display the progress of the download and generate the PDF files
    stdscr.clear()
    start_time = time.time()

    for i in range(len(all_image_data_lists)):
        stdscr.addstr(
            i,
            0,
            f'Downloading {processed_manga_data[int(selected_manga_index)]["title"]} [{processed_chapter_data[selected_chapters_indexes[i]]["chapter"]}]',
            curses.color_pair(1),
        )
        stdscr.refresh()

        generate_PDF(
            all_image_data_lists[i],
            f'{processed_manga_data[int(selected_manga_index)]["title"]} [{processed_chapter_data[selected_chapters_indexes[i]]["chapter"]}]',
        )

    elapsed_time = time.time() - start_time

    print(
        "\033[31m"
        + f"Finished downloading {len(all_image_data_lists)} chapters of {processed_manga_data[selected_manga_index]['title']} in {elapsed_time:.2f} seconds"
        + "\033[0m"
    )
    print("\033[31m" + f"Saved to {os.getcwd()}" + "\033[0m")

    # Close the session and exit the program
    await end()


def curses_main(stdscr: curses.window) -> None:
    # Run the start function in an asyncio.run to enable use of async/await
    asyncio.run(start(stdscr))


def main():
    # wrap curses_main in curses.wrapper to initialize curses
    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()
