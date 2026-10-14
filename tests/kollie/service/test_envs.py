import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from kollie.cluster.kustomization_request import PatchKustomizationRequest
from kollie.exceptions import KollieConfigError, KollieException
from kollie.models import KollieEnvironment, _datetime_from_str
from kollie.persistence.app_bundle import AppBundle
from kollie.persistence.app_template_store import AppTemplateStore
from kollie.service.applications import create_app, update_app
from kollie.service.envs import create_env, extend_lease, install_bundle
from tests.kollie.helpers import MagicAppTemplateSource, build_configmaps


@pytest.fixture(scope="function")
def mock_get_app_template_store():
    with patch("kollie.service.applications.get_app_template_store") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_get_kustomizations():
    with patch("kollie.service.applications.get_kustomizations") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_create_kustomization():
    with patch("kollie.service.applications.create_kustomization") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_create_owned_image_policy():
    with patch("kollie.service.applications.create_owned_image_policy") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_delete_env():
    with patch("kollie.service.envs.delete_env") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_get_app():
    with patch("kollie.service.applications.get_app") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_get_env():
    with patch("kollie.service.envs.get_env") as mock:
        yield mock


@patch("kollie.service.envs.create_env_configmap", autospec=True)
@patch("kollie.service.envs.create_git_repository", autospec=True)
def test_create_env_kustomization_not_exists(
    create_git_repository_mock,
    mock_create_env_configmap
):
    env_name = "test_env"
    owner_email = "test@example.com"

    create_env(
        env_name=env_name,
        owner_email=owner_email,
        flux_repo_branch=""
    )

    mock_create_env_configmap.assert_called_once_with(
        env_name=env_name,
        owner_email=owner_email,
        lease_exclusion_window=None,
    )
    create_git_repository_mock.assert_not_called()


@freeze_time("2024-01-19 15:03:08")
@patch("kollie.service.envs.create_env_configmap", autospec=True)
@patch("kollie.service.envs.create_git_repository", autospec=True)
def test_create_env_with_git_branch(
    create_git_repository_mock,
    mock_create_env_configmap
):
    mock_create_env_configmap.return_value.metadata.uid = "test_uid"

    env_name = "test_env"
    owner_email = "test@example.com"
    branch = "test-branch"

    create_env(
        env_name=env_name,
        owner_email=owner_email,
        flux_repo_branch=branch
    )

    create_git_repository_mock.assert_called_once_with(
        env_name=env_name,
        branch=branch,
        owner_email=owner_email,
        owner_uid=mock_create_env_configmap.return_value.metadata.uid
    )



@patch("kollie.service.envs.create_env_configmap")
def test_create_env_lease_exclusion(
    mock_create_env_configmap,
):
    owner_email = "test@example.com"
    os.environ["KOLLIE_LEASE_EXCLUSION_LIST"] = "env-one,excluded-perpetual-env"

    create_env(env_name="excluded-perpetual-env", owner_email=owner_email)

    mock_create_env_configmap.assert_called_once_with(
        env_name="excluded-perpetual-env",
        owner_email="test@example.com",
        lease_exclusion_window="Mon-Fri 07:00-19:00 Europe/London",
    )


@patch("kollie.service.applications.get_configmap")
def test_create_app_template_not_found_raises_config_error(
    mock_get_configmap,
    mock_create_owned_image_policy,
    mock_create_kustomization,
    mock_get_app_template_store,
):

    mock_get_app_template_store.return_value.get_by_name.return_value = None
    mock_get_configmap.return_value = build_configmaps(
        environments=[
            {
                "name": "test_env",
                "lease_exclusion_window": None,
                "owner_email": "test@owner.com",
            }
        ]
    )[0]

    with pytest.raises(KollieConfigError):
        env_name = "test_env"
        owner_email = "test@example.com"
        create_app(app_name="app1", env_name=env_name, owner_email=owner_email)

    mock_get_configmap.assert_called_once_with(name="test_env")

    mock_get_app_template_store.assert_called_once()
    mock_get_app_template_store.return_value.get_by_name.assert_called_once_with(
        app_name="app1"
    )

    mock_create_kustomization.assert_not_called()
    mock_create_owned_image_policy.assert_not_called()


@patch("kollie.service.applications.patch_kustomization")
def test_update_branch(
    mock_patch_kustomization,
    mock_get_app_template_store,
    mock_create_owned_image_policy,
    mock_get_app,
):
    mock_get_app_template_store.return_value.get_by_name.return_value = MagicMock()
    mock_patch_kustomization.return_value = {"metadata": {"uid": "test_uid"}}
    mock_get_app.return_value = Mock()

    update_app(env_name="test_env", app_name="test_app", attributes=dict(image_tag_prefix="main"))

    mock_get_app_template_store.return_value.get_by_name.assert_called_once_with(
        app_name="test_app"
    )

    mock_patch_kustomization.assert_called_once_with(
        PatchKustomizationRequest(
            env_name="test_env",
            app_name="test_app",
            body={"metadata": {"annotations": {"tails.com/tracking-image-tag-prefix": "main"}}},
        )
    )
    mock_create_owned_image_policy.assert_called_once_with(
        env_name="test_env",
        image_tag_prefix="main",
        app_template=mock_get_app_template_store.return_value.get_by_name.return_value,
        owner_uid=mock_patch_kustomization.return_value["metadata"]["uid"],
    )


def test_update_image_tag_refix_app_template_not_found_raises_config_error(
    mock_get_app_template_store, mock_get_app
):
    mock_get_app.return_value = None
    mock_get_app_template_store.return_value.get_by_name.return_value = None

    with pytest.raises(KollieException):
        update_app(
            env_name="test_env", app_name="test_app", attributes=dict(image_tag_prefix="main")
        )


@pytest.mark.parametrize(
    "date_str, expected_dt, raise_exception",
    [
        pytest.param(
            datetime(2024, 1, 19, 15, 3, 8).isoformat(),
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="python isoformat",
        ),
        pytest.param(
            "19-01-2024 15:03:08",
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="Legacy format",
        ),
        pytest.param(
            "2024-01-19T15:03:08.000",
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="ISO 8601 format",
        ),
        pytest.param(
            "2024-01-19T15:03:08",
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="ISO 8601 format without milliseconds",
        ),
        pytest.param(
            "2024-01-19 15:03:08",
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="ISO 8601 format with space",
        ),
        pytest.param(
            "2024-01-19 15:03:08.000",
            datetime(2024, 1, 19, 15, 3, 8),
            False,
            id="ISO 8601 format with space and milliseconds",
        ),
        pytest.param(
            "2024-01-19T15:03:08.000+00:00",
            datetime(2024, 1, 19, 15, 3, 8, tzinfo=UTC),
            False,
            id="ISO 8601 format with timezone",
        ),
        pytest.param(
            "2024-01-19T15:03:08.000Z",
            datetime(2024, 1, 19, 15, 3, 8, tzinfo=UTC),
            False,
            id="ISO 8601 format with Z also seems to work",
        ),
        pytest.param("19-01-2024", None, True, id="Invalid format"),
    ],
)
def test_datetime_from_str_formats(date_str, expected_dt, raise_exception):
    if raise_exception:
        with pytest.raises(ValueError):
            _datetime_from_str(date_str)
    else:
        assert _datetime_from_str(date_str) == expected_dt


@patch("kollie.service.envs.get_app_template_store")
@patch("kollie.service.envs.get_app_bundle_store")
@patch("kollie.service.envs.create_app")
def test_install_bundle_creates_expected_apps(
    mock_create_app,
    mock_get_app_bundle_store,
    mock_get_app_template_store,
    mock_get_env,
):
    # arrange
    app_names = ["foo", "bar", "baz"]

    mock_get_env.return_value = KollieEnvironment(
        name="test_env",
        owner_email="test@owner.com",
        apps=[Mock(name="foo")],
        flux_repository_branch=None
    )

    mock_get_app_template_store.return_value = AppTemplateStore(
        source=MagicAppTemplateSource(app_names=app_names)
    )

    mock_get_app_bundle_store.return_value.get_bundle.return_value = AppBundle(
        name="test_bundle",
        description="test_description",
        apps=["foo", "bar", "baz"],
    )

    # act
    install_bundle(
        env_name="test_env", bundle_name="test_bundle", owner_email="test@owner.com"
    )

    # assert
    assert mock_create_app.call_count == 3

    for app_name in app_names:
        mock_create_app.assert_any_call(
            app_name=app_name,
            image_tag_prefix="main",
            env_name="test_env",
            owner_email="test@owner.com",
        )


@freeze_time('2024-12-06')
@patch("kollie.service.envs.update_app")
def test_extend_lease_calls_update_app_with_expected_args(
    mock_update_app,
    mock_get_app,
    mock_get_env,
):
    app_name = Mock(name="foo")
    mock_get_env.return_value = KollieEnvironment(
        name="test_env",
        owner_email="test@owner.com",
        apps=[app_name],
        flux_repository_branch=None
    )
    mock_get_app.return_value = Mock()
    expected_arg = {
        'app_name': app_name.name,
        'env_name': 'test_env',
        'attributes': {
            'uptime_window': '2024-12-06T00:00:00+00:00-2024-12-08T10:00:00+00:00'
        }
    }

    extend_lease(env_name="test_env", hour=10, days=2)

    mock_update_app.assert_called_once_with(**expected_arg)
