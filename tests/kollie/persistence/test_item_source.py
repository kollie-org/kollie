from dataclasses import dataclass
from unittest.mock import mock_open, patch

import pytest

from kollie.persistence.item_source import JsonItemSource


@pytest.mark.parametrize(
    "from_file",
    [pytest.param(True, id="from_file"), pytest.param(False, id="from_str")],
)
def test_json_item_source(from_file: bool):
    # arrange
    @dataclass
    class TestData:
        foo: str
        bar: int

    raw_json = """
    [
        {"foo": "foo1", "bar": 1},
        {"foo": "foo2", "bar": 2}
    ]
    """

    # act
    if from_file:
        with patch(
            "kollie.persistence.item_source.open",
            mock_open(read_data=raw_json),
            create=True,
        ):
            item_source = JsonItemSource(
                item_type=TestData, json_path="/tmp/input.json"
            )
    else:
        item_source = JsonItemSource(item_type=TestData, json_str=raw_json)

    items = item_source.load()

    # assert
    assert len(items) == 2
    assert all(isinstance(item, TestData) for item in items)

    assert items[0].foo == "foo1"
    assert items[0].bar == 1
    assert items[1].foo == "foo2"
    assert items[1].bar == 2


def test_json_item_source_conditionally_required_args():

    with pytest.raises(ValueError):
        item_source = JsonItemSource(item_type=dict)
        item_source.load()
