from dataclasses import dataclass


@dataclass
class MenuOption:
    """A menu option for the main menu.

    Attributes:
        display_name: The text to display in the menu
        description: Brief description of the option
        screen: The Textual screen to navigate to
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
