from unittest.mock import MagicMock, patch
from pytest import fixture

from kollie.cluster.image_policy import create_owned_image_policy
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
