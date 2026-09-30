from dataclasses import dataclass

from .screen_names import ScreenName


@dataclass(frozen=True)
class MenuOption:
    """Container for menu options with display and navigation data."""

    display_name: str
    description: str
    screen: str


MENU_OPTIONS: tuple[MenuOption, ...] = (
    MenuOption(
        display_name="Search",
        description="Search for manga and download chapters.",
        screen=ScreenName.SEARCH.value,
    ),
    MenuOption(
        display_name="Favorites",
        description="Manage your list of favorite manga.",
        screen=ScreenName.FAVORITES.value,
    ),
    MenuOption(
        display_name="Downloads",
        description="View downloads from this session in real time.",
        screen=ScreenName.DOWNLOADS.value,
    ),
    MenuOption(
        display_name="Settings",
        description="Configure the application settings.",
        screen=ScreenName.SETTINGS.value,
    ),
)
