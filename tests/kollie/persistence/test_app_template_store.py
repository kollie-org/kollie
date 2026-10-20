from unittest.mock import Mock

import pytest

from kollie.persistence import (
    AppTemplate,
    AppTemplateStore,
    ImageRepositoryRef,
    JsonFileAppTemplateSource,
    get_app_template_store,
)


@pytest.fixture
def mock_app_template_source():
    source = Mock()
    source.load.return_value = [
        AppTemplate(
            app_name="test_app",
            label="test_label",
            git_repository_name="flux-test-repo",
            git_repository_path="bob/builder",
            image_repository_ref=ImageRepositoryRef(
                name="test_repo", namespace="test_namespace"
            ),
            default_image_tag_prefix="main",
        ),
        AppTemplate(
            app_name="test_app_2",
            label="test_label_2",
            git_repository_name="flux-test-repo-2",
            git_repository_path="bob/builder",
            image_repository_ref=ImageRepositoryRef(
                name="test_repo_2", namespace="test_namespace_2"
            ),
            default_image_tag_prefix="thingsandstuff-main",
        ),
    ]
    return source


def test_get_by_name(mock_app_template_source):
    store = AppTemplateStore(source=mock_app_template_source)

    result = store.get_by_name("test_app")

    assert result.app_name == "test_app"
    assert result.label == "test_label"


def test_get_all(mock_app_template_source):
    store = AppTemplateStore(source=mock_app_template_source)

    templates = store.get_all()

    assert len(templates) == 2
    assert templates[0].app_name == "test_app"
    assert templates[0].label == "test_label"
    assert templates[1].app_name == "test_app_2"
    assert templates[1].label == "test_label_2"


def test_get_app_template_store_with_valid_env():
    store = get_app_template_store()

    assert isinstance(store, AppTemplateStore)
    assert isinstance(store._source, JsonFileAppTemplateSource)
