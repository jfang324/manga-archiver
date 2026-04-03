from typing import TypedDict


class ProcessedManga(TypedDict):
    id: str
    title: str


class ProcessedChapter(TypedDict):
    id: str
    title: str
    chapter: str


class ProcessedDownloadResource(TypedDict):
    hash: str
    urls: list[str]
