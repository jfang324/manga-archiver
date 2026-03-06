"""Curses-based UI components."""

from typing import Any, Mapping, Optional, TypeVar

import curses

T = TypeVar("T", bound=Mapping[str, Any])


def prompt_user_input(stdscr: curses.window, message: str) -> str:
    """Prompt the user to enter a string and returns the string entered.

    :param stdscr: The curses window object
    :param message: The message to display to the user
    :return: The string entered by the user
    """
    curses.curs_set(1)
    user_input: str = ""

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"{message}: ", curses.color_pair(1))
        stdscr.addstr(f"{user_input}")

        key = stdscr.getch()
        if key in [ord("\n"), curses.KEY_ENTER]:
            break
        elif key in [ord("\b"), curses.KEY_BACKSPACE]:
            user_input = user_input[:-1]
        elif key == 27:  # ESC key
            user_input = ""
            break
        else:
            if 32 <= key <= 126:
                user_input += chr(key)

    curses.curs_set(0)
    return user_input


def display_list(
    stdscr: curses.window,
    result_list: list[T],
    page_start: int,
    page_end: int,
    current_index: int,
    selected_indexes: set[int],
) -> None:
    """Display the result list with highlighting for selected items.

    :param stdscr: The curses window object
    :param result_list: The list of items to display
    :param page_start: The starting index of the current page
    :param page_end: The ending index of the current page
    :param current_index: The currently selected index
    :param selected_indexes: The set of selected indexes
    """
    for i in range(page_start, page_end):
        if i == current_index:
            stdscr.addstr(i - page_start + 2, 0, "> ", curses.color_pair(2))
            if i in selected_indexes:
                if "chapter" in result_list[i]:
                    stdscr.addstr(
                        f"{result_list[i]['chapter']} {result_list[i]['title']}",
                        curses.color_pair(3),
                    )
                else:
                    stdscr.addstr(
                        f" {result_list[i]['title']}",
                        curses.color_pair(3),
                    )
            else:
                if "chapter" in result_list[i]:
                    stdscr.addstr(
                        f"{result_list[i]['chapter']} {result_list[i]['title']}",
                        curses.A_REVERSE,
                    )
                else:
                    stdscr.addstr(
                        f" {result_list[i]['title']}",
                        curses.A_REVERSE,
                    )
        else:
            if i in selected_indexes:
                stdscr.addstr(i - page_start + 2, 0, " ", curses.A_REVERSE)
                stdscr.addstr(" ")
                if "chapter" in result_list[i]:
                    stdscr.addstr(
                        f"{result_list[i]['chapter']} {result_list[i]['title']}",
                        curses.color_pair(3),
                    )
                else:
                    stdscr.addstr(
                        f" {result_list[i]['title']}",
                        curses.color_pair(3),
                    )
            else:
                stdscr.addstr(i - page_start + 2, 0, " ", curses.A_REVERSE)
                stdscr.addstr(" ")
                if "chapter" in result_list[i]:
                    stdscr.addstr(
                        f"{result_list[i]['chapter']} {result_list[i]['title']}",
                    )
                else:
                    stdscr.addstr(f" {result_list[i]['title']}")


def prompt_list_selection(
    stdscr: curses.window,
    result_list: list[T],
    page_size: int,
    title: str,
) -> Optional[int]:
    """Display result list and prompt user to select an item.

    :param stdscr: The curses window object
    :param result_list: The list of items to display
    :param page_size: The number of results to display per page
    :param title: The title at the top of the list
    :return: The index of the selected item, or None if cancelled
    """
    current_index: int = 0

    while True:
        stdscr.clear()
        page_start: int = (current_index // page_size) * page_size
        page_end: int = min(page_start + page_size, len(result_list))

        # Display header
        stdscr.addstr(0, 0, f"{title}:", curses.color_pair(1))
        stdscr.addstr(1, 0, "Use ", curses.color_pair(1))
        stdscr.addstr("↑/↓", curses.color_pair(4))
        stdscr.addstr(" for navigation, ", curses.color_pair(1))
        stdscr.addstr("ESC", curses.color_pair(4))
        stdscr.addstr(" to exit, ", curses.color_pair(1))
        stdscr.addstr("ENTER", curses.color_pair(4))
        stdscr.addstr(" to select.", curses.color_pair(1))

        # Display list
        display_list(
            stdscr,
            result_list,
            page_start,
            page_end,
            current_index,
            set(),
        )

        # Display footer
        stdscr.addstr(
            f"\n{page_start + 1}-{page_end} of {len(result_list)} results",
            curses.color_pair(1),
        )
        stdscr.refresh()

        # Process input
        key: int = stdscr.getch()

        if key == curses.KEY_UP:
            current_index = max(current_index - 1, 0)
        elif key == curses.KEY_DOWN:
            current_index = min(current_index + 1, len(result_list) - 1)
        elif key == ord("\n"):
            return current_index
        elif key == 27:  # ESC key
            return None


def prompt_list_multi_selection(
    stdscr: curses.window,
    result_list: list[T],
    page_size: int,
    title: str,
) -> Optional[list[int]]:
    """Display result list and prompt user to select multiple items.

    :param stdscr: The curses window object
    :param result_list: The list of items to display
    :param page_size: The number of results to display per page
    :param title: The title at the top of the list
    :return: List of selected indexes, or None if cancelled
    """
    selected_indexes: set[int] = set()
    current_index: int = 0

    while True:
        stdscr.clear()
        page_start: int = (current_index // page_size) * page_size
        page_end: int = min(page_start + page_size, len(result_list))

        # Display header
        stdscr.addstr(0, 0, f"{title}:", curses.color_pair(1))
        stdscr.addstr(1, 0, "Use ", curses.color_pair(1))
        stdscr.addstr("↑/↓", curses.color_pair(4))
        stdscr.addstr(" for navigation, ", curses.color_pair(1))
        stdscr.addstr("←", curses.color_pair(4))
        stdscr.addstr(" to select, ", curses.color_pair(1))
        stdscr.addstr("ESC", curses.color_pair(4))
        stdscr.addstr(" to exit, ", curses.color_pair(1))
        stdscr.addstr("ENTER", curses.color_pair(4))
        stdscr.addstr(" to download.", curses.color_pair(1))

        # Display list
        display_list(
            stdscr,
            result_list,
            page_start,
            page_end,
            current_index,
            selected_indexes,
        )

        # Display footer
        stdscr.addstr(
            f"\n{page_start + 1}-{page_end} of {len(result_list)} results",
            curses.color_pair(1),
        )
        stdscr.refresh()

        # Process input
        key: int = stdscr.getch()

        if key == curses.KEY_UP:
            current_index = max(current_index - 1, 0)
        elif key == curses.KEY_DOWN:
            current_index = min(current_index + 1, len(result_list) - 1)
        elif key == curses.KEY_LEFT:
            if current_index in selected_indexes:
                selected_indexes.remove(current_index)
            else:
                selected_indexes.add(current_index)
        elif key == ord("\n"):
            return list(selected_indexes)
        elif key == 27:  # ESC key
            return None
