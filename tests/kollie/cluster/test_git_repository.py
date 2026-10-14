from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kollie.cluster.constants import DEFAULT_FLUX_REPOSITORY, KOLLIE_NAMESPACE
from kollie.cluster.git_repository import (
    GROUP,
    OBJECT_PLURAL,
    VERSION,
    create_git_repository,
    get_git_repository,
)
from kollie.exceptions import (
    CreateCustomObjectsApiException,
    GetCustomObjectsApiException,
)


@pytest.fixture(autouse=True)
def mock_kube_client():
    with patch("kollie.cluster.git_repository.client") as mock_client:
        yield mock_client


@patch("kollie.cluster.git_repository_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.git_repository_request.V1OwnerReference", new=dict)
def test_create_git_repository(mock_kube_client):
    # arrange
    mock_git_repository_response = {
        "apiVersion": "source.toolkit.fluxcd.io/v1",
        "kind": "GitRepository",
        "metadata": {
            "labels": {
                "tails-app-environment": "test_env",
                "tails-app-stage": "testing"
            },
            "name": "test-repo-test-b",
            "namespace": "kollie",
            "uid": "12ff8861-f221-4d8f-837d-b3d4d4a26199"
        },
        "spec": {
            "interval": "5m",
            "ref": {
                "branch": "test-branch"
            },
        },
        "status": {
            "observedGeneration": -1
        }
    }

    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.create_namespaced_custom_object.return_value = (
        mock_git_repository_response
    )

    env_name = "test_env"
    branch = "test-branch"
    owner_email = "test@owner.com"
    owner_uid = "test_uid"

    # act
    git_repository = create_git_repository(
        env_name=env_name,
        branch=branch,
        owner_email=owner_email,
        owner_uid=owner_uid
    )

    # assert
    assert git_repository == mock_git_repository_response

    mock_api.create_namespaced_custom_object.assert_called_once_with(
        group=GROUP,
        version=VERSION,
        namespace="kollie",
        plural=OBJECT_PLURAL,
        body={
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {
                "name": "test-repo-test_env",
                "namespace": KOLLIE_NAMESPACE,
                "labels": {
                    "tails-app-stage": "testing",
                    "tails-app-environment": env_name,
                },
                "annotations": {
                    "tails.com/owner": owner_email,
                    "tails.com/tracking-branch": branch,
                },
                "owner_references": [
                    {
                        "api_version": "v1",
                        "name": env_name,
                        "block_owner_deletion": True,
                        "uid": owner_uid,
                        "kind": "ConfigMap",
                    },
                ],
            },
            "spec": {
                "interval": "5m",
                "ref": {"branch": branch},
                "secretRef": {"name": DEFAULT_FLUX_REPOSITORY},
                "url": f"ssh://git@github.com/tailsdotcom/{DEFAULT_FLUX_REPOSITORY}",
            },
        }
    )


@patch("kollie.cluster.git_repository_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.git_repository_request.V1OwnerReference", new=dict)
def test_create_git_repository_error(mock_kube_client):
    # arrange
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.create_namespaced_custom_object.side_effect = ApiException(
        status=500, reason="Something went wrong"
    )

    env_name = "test_env"
    branch = "test_branch"
    owner_email = "test@owner.com"
    owner_uid = "test_uid"

    # act
    with pytest.raises(CreateCustomObjectsApiException) as exc:
        create_git_repository(
            env_name=env_name,
            branch=branch,
            owner_email=owner_email,
            owner_uid=owner_uid
        )

    # assert
    assert exc.value.custom_object == OBJECT_PLURAL


def test_get_git_repository(mock_kube_client):
    # arrange
    mock_response = {
        "apiVersion": "source.toolkit.fluxcd.io/v1",
        "kind": "GitRepository",
        "metadata": {
            "labels": {
                "tails-app-environment": "test_env",
                "tails-app-stage": "testing"
            },
            "name": "test-repo-test-env",
            "namespace": "kollie",
            "uid": "12ff8861-f221-4d8f-837d-b3d4d4a26199"
        },
        "spec": {
            "interval": "5m",
            "ref": {
                "branch": "test-branch"
            },
        }
    }
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.get_namespaced_custom_object.return_value = mock_response

    # act
    git_repository = get_git_repository(env_name="test_env")

    # assert
    assert git_repository == mock_response


def test_get_git_repository_none(mock_kube_client):
    # arrange
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.get_namespaced_custom_object.side_effect = ApiException(
        status=404, reason="Not found"
    )

    # act
    git_repository = get_git_repository(env_name="test_env")

    # assert
    assert git_repository is None


def test_get_git_repository_error(mock_kube_client):
    # arrange
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.get_namespaced_custom_object.side_effect = ApiException(
        status=500, reason="Something went wrong"
    )

    # act
    with pytest.raises(GetCustomObjectsApiException) as exc:
        get_git_repository(env_name="test_env")

    # assert
    assert exc.value.custom_object == OBJECT_PLURAL
