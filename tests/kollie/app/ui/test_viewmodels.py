import pytest

from kollie.app.ui.viewmodels import IngressView, render_resources
from kollie.models import KollieApp


@pytest.fixture
def model():
    return KollieApp(
        name="app",
        env_name="env",
        owner_email="owner",
        image_tag="tag",
        image_tag_prefix="branch",
    )


@pytest.fixture
def mock_tpl(mocker):
    mock_tpl = mocker.MagicMock()
    mock_tpl.env.get_template().render.return_value = "rendered template"

    return mock_tpl


def test_ingress_view_template(model):
    view = IngressView(model)
    assert view.template == "/apps/ingress.jinja2"


def test_ingress_view_get_info_with_urls(model):
    model.urls = ["http://example.com"]
    view = IngressView(model)
    assert view.build_context() == {"urls": ["http://example.com"]}


def test_ingress_view_get_info_without_urls(model):
    view = IngressView(model)
    assert view.build_context() == {"urls": []}


def test_ingress_view_render(mocker, model):
    model.urls = ["http://example.com"]
    view = IngressView(model)
    mock_templates = mocker.MagicMock()

    mock_get_template = mocker.patch.object(mock_templates.env, "get_template")
    mock_template = mock_get_template.return_value
    mock_render = mocker.patch.object(
        mock_template, "render", return_value="rendered template"
    )

    result = view.render(mock_templates)

    mock_get_template.assert_called_once_with("/apps/ingress.jinja2")
    mock_render.assert_called_once_with(urls=["http://example.com"])
    assert result == "rendered template"


def test_app_view_get_resources_with_urls(model, mock_tpl):
    model.urls = ["http://example.com"]
    resources = render_resources(model, mock_tpl)
    assert len(resources) == 1
    assert isinstance(resources[0], str)


def test_app_view_get_resources_without_urls(model, mock_tpl):
    resources = render_resources(model, mock_tpl)
    assert len(resources) == 0
