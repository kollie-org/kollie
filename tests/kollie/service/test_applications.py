from unittest.mock import Mock, patch

import pytest

from kollie.exceptions import KollieConfigError
from kollie.persistence.app_template import AppTemplate
from kollie.service.applications import create_app, update_app
from kollie.service.envs import install_bundle
from tests.kollie.helpers import build_configmaps


@patch("kollie.service.applications.get_app_template_store")
@patch("kollie.service.applications.patch_kustomization")
@patch("kollie.service.applications.get_app")
def test_update_image_tag_prefix_app_template_not_found_raises_config_error(
    mock_get_app,
    mock_patch_kustomization,
    mock_get_app_template_store,
):
    mock_get_app_template_store.return_value.get_by_name.return_value = None
    mock_patch_kustomization.return_value = {"metadata": {"uid": "test_uid"}}
    mock_get_app.return_value = Mock()

    with pytest.raises(KollieConfigError):
        update_app(
            env_name="test_env", app_name="test_app", attributes=dict(image_tag_prefix="main")
        )


@patch("kollie.service.envs.get_env")
@patch("kollie.service.envs.get_app_bundle_store")
def test_install_bundle_raises_config_error_when_bundle_not_found(
    mock_get_app_bundle_store, mock_get_env
):
    # arrange
    mock_get_app_bundle_store.return_value.get_bundle.return_value = None
    mock_get_env.return_value = Mock()

    # act
    with pytest.raises(KollieConfigError):
        install_bundle(
            env_name="test_env", bundle_name="test_bundle", owner_email="test@owner.com"
        )


@patch("kollie.service.envs.get_env")
@patch("kollie.service.envs.get_app_bundle_store")
def test_install_bundle_raises_config_error_when_env_not_found(
    mock_get_app_bundle_store, mock_get_env
):
    # arrange
    mock_get_app_bundle_store.return_value.get_bundle.return_value = Mock()
    mock_get_env.return_value = None

    # act
    with pytest.raises(KollieConfigError):
        install_bundle(
            env_name="test_env", bundle_name="test_bundle", owner_email="test@owner.com"
        )


@patch("kollie.service.applications.get_configmap", autospec=True)
@patch("kollie.service.applications.create_owned_image_policy", autospec=True)
@patch("kollie.service.applications.create_kustomization", autospec=True)
@patch("kollie.service.applications.get_app_template_store", autospec=True)
@patch("kollie.service.applications.get_git_repository", autospec=True)
def test_create_app_defaults_to_branch_from_app_template(
    mock_get_git_repository,
    mock_get_app_template_store,
    mock_create_kustomization,
    mock_create_owned_image_policy,
    mock_get_configmap,
):
    # arrange
    template = AppTemplate.from_dict(
        data={
            "app_name": "test_app",
            "label": "test_label",
            "git_repository_name": "test-flux-repo",
            "git_repository_path": "bob/builder",
            "image_repository_ref": {
                "name": "test_repo",
                "namespace": "test_namespace",
            },
            "default_image_tag_prefix": "mctest",
        }
    )

    mock_get_configmap.return_value = build_configmaps(
        environments=[
            {
                "name": "test_env",
                "lease_exclusion_window": None,
                "owner_email": "test@owner.com",
            },
        ]
    )[0]
    mock_get_app_template_store.return_value.get_by_name.return_value = template
    mock_get_git_repository.return_value = None

    # act
    create_app(app_name="test_app", env_name="test_env", owner_email="test@owner.com")

    # assert
    mock_get_app_template_store.return_value.get_by_name.assert_called_once_with(
        app_name="test_app"
    )

    mock_create_kustomization.assert_called_once_with(
        env_name="test_env",
        image_tag_prefix="mctest",
        app_template=template,
        owner_email="test@owner.com",
        owner_uid=mock_get_configmap.return_value.metadata.uid,
        lease_exclusion_window=None,
        git_repository_name=None,
    )

    mock_create_owned_image_policy.assert_called_once_with(
        env_name="test_env",
        image_tag_prefix="mctest",
        app_template=template,
        owner_uid=mock_create_kustomization.return_value["metadata"]["uid"],
    )


@patch("kollie.service.applications.get_configmap", autospec=True)
@patch("kollie.service.applications.create_owned_image_policy", autospec=True)
@patch("kollie.service.applications.create_kustomization", autospec=True)
@patch("kollie.service.applications.get_app_template_store", autospec=True)
@patch("kollie.service.applications.get_git_repository", autospec=True)
def test_create_app_with_git_repository_in_env(
    mock_get_git_repository,
    mock_get_app_template_store,
    mock_create_kustomization,
    mock_create_owned_image_policy,
    mock_get_configmap,
):
    # arrange
    template = AppTemplate.from_dict(
        data={
            "app_name": "test_app",
            "label": "test_label",
            "git_repository_name": "test-flux-repo",
            "git_repository_path": "bob/builder",
            "image_repository_ref": {
                "name": "test_repo",
                "namespace": "test_namespace",
            },
            "default_image_tag_prefix": "mctest",
        }
    )

    mock_get_configmap.return_value = build_configmaps(
        environments=[
            {
                "name": "test_env",
                "owner_email": "test@owner.com",
            },
        ]
    )[0]
    mock_get_app_template_store.return_value.get_by_name.return_value = template
    mock_get_git_repository.return_value = {"metadata": {"name": "test-git-repo"}}

    # act
    create_app(app_name="test_app", env_name="test_env", owner_email="test@owner.com")

    # assert
    mock_create_kustomization.assert_called_once_with(
        env_name="test_env",
        image_tag_prefix="mctest",
        app_template=template,
        owner_email="test@owner.com",
        owner_uid=mock_get_configmap.return_value.metadata.uid,
        lease_exclusion_window=None,
        git_repository_name="test-git-repo",
    )
