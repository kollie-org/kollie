from unittest.mock import MagicMock, patch

from kubernetes.client import ApiException
from pytest import fixture, raises

from kollie.cluster.image_policy import create_owned_image_policy
from kollie.exceptions import KollieImagePolicyException
from kollie.persistence import AppTemplate, ImageRepositoryRef


@fixture()
def mock_kube_client():
    with patch("kollie.cluster.image_policy.client") as mock_client:
        yield mock_client


def test_create_owned_image_policy(mock_kube_client):
    """Test that the ImagePolicy is created with the correct parameters."""
    app_template = AppTemplate(
        app_name="test_app",
        label="test_label",
        git_repository_name="test-flux-repo",
        git_repository_path="bob/builder",
        image_repository_ref=ImageRepositoryRef(
            name="test_repo", namespace="test_namespace"
        ),
        default_image_tag_prefix="default_image_tag_prefix",
    )

    mock_api = MagicMock()
    mock_kube_client.V1ObjectMeta = dict
    mock_kube_client.V1OwnerReference = dict
    mock_kube_client.CustomObjectsApi.return_value = mock_api

    create_owned_image_policy(
        env_name="test_env",
        image_tag_prefix="test_tag_prefix",
        app_template=app_template,
        owner_uid="test_uid",
        owner_kind="test_kind",
    )

    expected_body = {
        "apiVersion": "image.toolkit.fluxcd.io/v1",
        "kind": "ImagePolicy",
        "metadata": {
            "name": "test_env-test_app",
            "labels": {
                "tails-app-stage": "testing",
                "tails-app-environment": "test_env",
                "tails-app-name": "test_app",
            },
            "owner_references": [
                {
                    "api_version": "kustomize.toolkit.fluxcd.io/v1",
                    "name": "test_env-test_app",
                    "block_owner_deletion": True,
                    "uid": "test_uid",
                    "kind": "test_kind",
                }
            ],
        },
        "spec": {
            "imageRepositoryRef": {
                "name": "test_repo",
                "namespace": "test_namespace",
            },
            "filterTags": {
                "pattern": "^test_tag_prefix-[a-fA-F0-9]+-(?P<ts>.*)",
                "extract": "$ts",
            },
            "policy": {"numerical": {"order": "asc"}},
        },
    }

    mock_api.create_namespaced_custom_object.assert_called_once_with(
        group="image.toolkit.fluxcd.io",
        version="v1",
        namespace="kollie",
        plural="imagepolicies",
        body=expected_body,
    )


@fixture()
def app_template():
    return AppTemplate(
        app_name="test_app",
        label="test_label",
        git_repository_name="test-flux-repo",
        git_repository_path="bob/builder",
        image_repository_ref=ImageRepositoryRef(
            name="test_repo", namespace="test_namespace"
        ),
        default_image_tag_prefix="default_image_tag_prefix",
    )


@fixture()
def mock_api(mock_kube_client):
    mock_api = MagicMock()
    mock_kube_client.V1ObjectMeta = dict
    mock_kube_client.V1OwnerReference = dict
    mock_kube_client.ApiException = ApiException
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.create_namespaced_custom_object.side_effect = ApiException(status=409)
    return mock_api


def test_create_owned_image_policy_updates_existing_policy(mock_api, app_template):
    """Test that an existing ImagePolicy is patched in place on 409."""
    mock_api.get_namespaced_custom_object.return_value = {"metadata": {}}

    create_owned_image_policy(
        env_name="test_env",
        image_tag_prefix="new_prefix",
        app_template=app_template,
        owner_uid="test_uid",
    )

    body = mock_api.create_namespaced_custom_object.call_args.kwargs["body"]
    mock_api.patch_namespaced_custom_object.assert_called_once_with(
        group="image.toolkit.fluxcd.io",
        version="v1",
        namespace="kollie",
        plural="imagepolicies",
        name="test_env-test_app",
        body=body,
    )
    assert body["spec"]["filterTags"]["pattern"] == (
        "^new_prefix-[a-fA-F0-9]+-(?P<ts>.*)"
    )


def test_create_owned_image_policy_raises_when_policy_is_being_deleted(
    mock_api, app_template
):
    """Test that a policy that is being deleted is not patched."""
    mock_api.get_namespaced_custom_object.return_value = {
        "metadata": {"deletionTimestamp": "2026-10-13T14:45:59Z"}
    }

    with raises(KollieImagePolicyException):
        create_owned_image_policy(
            env_name="test_env",
            image_tag_prefix="new_prefix",
            app_template=app_template,
            owner_uid="test_uid",
        )

    mock_api.patch_namespaced_custom_object.assert_not_called()


def test_create_owned_image_policy_raises_when_patch_fails(mock_api, app_template):
    """Test that a failed patch raises the Kollie exception, not the API one."""
    mock_api.get_namespaced_custom_object.return_value = {"metadata": {}}
    mock_api.patch_namespaced_custom_object.side_effect = ApiException(status=422)

    with raises(KollieImagePolicyException):
        create_owned_image_policy(
            env_name="test_env",
            image_tag_prefix="new_prefix",
            app_template=app_template,
            owner_uid="test_uid",
        )


def test_create_owned_image_policy_raises_on_other_errors(mock_api, app_template):
    """Test that errors other than 409 are not treated as an existing policy."""
    mock_api.create_namespaced_custom_object.side_effect = ApiException(status=403)

    with raises(KollieImagePolicyException):
        create_owned_image_policy(
            env_name="test_env",
            image_tag_prefix="new_prefix",
            app_template=app_template,
            owner_uid="test_uid",
        )

    mock_api.get_namespaced_custom_object.assert_not_called()
    mock_api.patch_namespaced_custom_object.assert_not_called()
