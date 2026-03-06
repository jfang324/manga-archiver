from typing import Optional, TypedDict


class ProcessedManga(TypedDict):
    title: str
    id: str


class ProcessedChapter(TypedDict):
    title: Optional[str]
    id: str
    chapter: str


class ProcessedDownloadResource(TypedDict):
    urls: list[str]
    hash: str
