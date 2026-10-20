import os
from collections.abc import Sequence
from dataclasses import dataclass

from kollie.persistence.item_source import ItemSource, JsonItemSource


@dataclass
class AppBundle:
    name: str
    description: str
    apps: Sequence[str]


class AppBundleStore:
    def __init__(self, app_bundle_source: ItemSource[AppBundle]):
        self._bundles = {bundle.name: bundle for bundle in app_bundle_source.load()}

    def get_bundle(self, name: str) -> AppBundle | None:
        return self._bundles.get(name)

    def get_all_bundles(self) -> list[AppBundle]:
        return list(self._bundles.values())


def get_app_bundle_store() -> AppBundleStore:

    json_path = os.getenv("KOLLIE_APP_BUNDLE_JSON_PATH", "app_bundles.json")

    return AppBundleStore(
        app_bundle_source=JsonItemSource(json_path=json_path, item_type=AppBundle)
    )
