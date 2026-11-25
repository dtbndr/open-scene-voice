from dataclasses import dataclass

from .record_item import RecordItem


@dataclass(frozen=True)
class RecordRead:
    """The record on disk: state `none`, `ok` (items in file order) or `unreadable`."""

    state: str
    items: tuple[RecordItem, ...] = ()
