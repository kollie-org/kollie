import json
from typing import Generic, Protocol, TypeVar

ItemType = TypeVar("ItemType")


class JsonItemSource(Generic[ItemType]):
    """
    Generic JSON reader for any dataclass.
    """

    def __init__(
        self,
        item_type: type[ItemType],
        json_path: str | None = None,
        json_str: str | None = None,
    ) -> None:
        """
        item_type: The dataclass to hydrate json items into.
        json_path: The path to the json file.
        json_str: The json string.

        One of json_path or json_str must be provided.
        json_str takes precedence over json_path.
        """
        self.json_str: str = ""
        self.item_type = item_type

        if json_str is not None:
            self.json_str = json_str
        else:
            if json_path is None:
                raise ValueError("Either json_path or json_str must be provided")

            self.json_str = self.read_file(json_path)

    def read_file(self, json_path: str) -> str:
        with open(json_path, "r") as source_file:
            return source_file.read()

    def load(self) -> list[ItemType]:
        return [self.item_type(**raw_item) for raw_item in json.loads(self.json_str)]


class ItemSource(Protocol, Generic[ItemType]):

    def load(self) -> list[ItemType]: ...
