from dataclasses import dataclass


@dataclass
class MenuOption:
    """
    A data container for each option in the main menu.

    Attributes:
        display_name (str): The display name of the option.
        description (str): A short description of the option.
        screen (str): The Textual screen to display when the option is selected.
    """

    display_name: str
    description: str
    screen: str


MENU_OPTIONS = [
    MenuOption(
        display_name="Search",
        description="Search for manga and download chapters.",
        screen="search_screen",
    ),
    MenuOption(
        display_name="Favorites",
        description="Manage your list of favorite manga.",
        screen="favorites_screen",
    ),
    MenuOption(
        display_name="Downloads",
        description="View downloads from this session in real time.",
        screen="downloads_screen",
    ),
    MenuOption(
        display_name="Settings",
        description="Configure the application settings.",
        screen="settings_screen",
    ),
]
