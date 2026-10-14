import json
from unittest.mock import mock_open, patch

import pytest

from kollie.persistence import AppTemplate, JsonFileAppTemplateSource


def test_json_file_app_template_source_load():
    mock_file_content = json.dumps(
        [
            {
                "app_name": "test_app",
                "label": "test_label",
                "git_repository_path": "bob/builder",
                "image_repository_ref": {
                    "name": "test_repo",
                    "namespace": "test_namespace",
                },
                "default_image_tag_prefix": "main",
            }
        ]
    )
    mock_open_func = mock_open(read_data=mock_file_content)

    with patch("builtins.open", mock_open_func):
        source = JsonFileAppTemplateSource(json_path="dummy_path")
        templates = source.load()

    assert len(templates) == 1
    assert isinstance(templates[0], AppTemplate)
    assert templates[0].app_name == "test_app"
    assert templates[0].label == "test_label"
    assert templates[0].git_repository_name == "test-repo"
    assert templates[0].git_repository_path == "bob/builder"
    assert templates[0].image_repository_ref.name == "test_repo"
    assert templates[0].image_repository_ref.namespace == "test_namespace"
    assert templates[0].default_image_tag_prefix == "main"


def test_load_raises_json_decode_error():
    mock_file = mock_open(read_data='{"invalid json"}')
    with patch("builtins.open", mock_file):
        source = JsonFileAppTemplateSource("/dummy_path/file.json")
        with pytest.raises(ValueError):
            source.load()


def test_load_returns_empty_list_when_file_is_empty():
    mock_file = mock_open(read_data="")
    with patch("builtins.open", mock_file):
        source = JsonFileAppTemplateSource("/dummy_path/file.json")
        templates = source.load()
        assert templates == []
