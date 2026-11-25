from collections.abc import Iterator, Mapping

from .route_table import Handler, RouteTable


class ChainedRoutes(Mapping[str, Mapping[str, Handler]]):
    """The keys dict first, then the project routes; size and iteration are the keys dict's."""

    def __init__(self, first: RouteTable, second: RouteTable) -> None:
        self._first = first
        self._second = second

    def __getitem__(self, path: str) -> Mapping[str, Handler]:
        if path in self._first:
            return self._first[path]
        return self._second[path]

    def __iter__(self) -> Iterator[str]:
        return iter(self._first)

    def __len__(self) -> int:
        return len(self._first)


def chain_routes(first: RouteTable, second: RouteTable) -> ChainedRoutes:
    return ChainedRoutes(first, second)
