from copy import deepcopy
from unittest.mock import MagicMock, Mock, patch

from freezegun import freeze_time
from pytest import fixture

from kollie.cluster.constants import KOLLIE_NAMESPACE
from kollie.cluster.kustomization import (
    create_kustomization,
    delete_kustomizations,
    get_kustomizations,
)

DEFAULT_REQUST_BODY = {
    "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
    "kind": "Kustomization",
    "metadata": {
        "labels": {
            "tails-app-stage": "testing",
        },
        "annotations": {
            "tails.com/owner": "test@test.local",
            "tails.com/tracking-image-tag-prefix": "main"
        },
        "owner_references": [
            {
                "api_version": "v1",
                "block_owner_deletion": True,
                "kind": "ConfigMap",
                "uid": "test_uid"
            }
        ]
    },
    "spec": {
        "interval": "5m",
        "sourceRef": {
            "kind": "GitRepository",
            "namespace": "flux-system"
        },
        "prune": True,
        "postBuild": {
            "substitute": {
                "aws_account": "1234",
                "ecr_mirror": "5678",
                "stage": "testing",
                "zone_name": "testenvs.example.com",
                "downscaler_uptime": "2024-01-01T00:00:00+00:00-2024-01-01T19:00:00+00:00",
            }
        }
    },
}


@fixture(autouse=True)
def mock_kube_client():
    with patch("kollie.cluster.kustomization.client") as mock_client:
        yield mock_client


@fixture
def mock_request_setup(mock_kube_client):
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api

    app_template = Mock()
    app_template.app_name = "pricing-service"
    app_template.label = "test_label_2"
    app_template.git_repository_name = "test-flux-repo"
    app_template.git_repository_path = "bob/builder"
    app_template.default_image_tag_prefix = "main"

    image_repository_ref = Mock()
    image_repository_ref.name = "test_repo_2"
    image_repository_ref.namespace = "test_namespace_2"

    app_template.image_repository_ref = image_repository_ref

    return {
        "mock_api": mock_api,
        "app_template": app_template
    }


def test_get_kustomizations(mock_kube_client):
    # arrange
    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    mock_api.list_namespaced_custom_object.return_value = {
        "items": [{"metadata": {"name": "test-kustomization"}}]
    }

    # act
    kustomizations = get_kustomizations()

    # assert
    assert isinstance(kustomizations, list)
    assert len(kustomizations) == 1
    assert kustomizations[0]["metadata"]["name"] == "test-kustomization"


@freeze_time("2024-01-01")
@patch("kollie.cluster.kustomization_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.kustomization_request.V1OwnerReference", new=dict)
def test_create_kustomization(mock_request_setup):
    # arrange
    testenv_name = "feature-foo"
    app_template = mock_request_setup["app_template"]
    mock_api = mock_request_setup["mock_api"]

    # act
    create_kustomization(
        env_name=testenv_name,
        image_tag_prefix=app_template.default_image_tag_prefix,
        app_template=app_template,
        owner_email="test@test.local",
        owner_uid="test_uid",
        lease_exclusion_window=None,
    )

    # assert
    req_body = deepcopy(DEFAULT_REQUST_BODY)

    req_body["metadata"]["name"] = f"{testenv_name}-{app_template.app_name}"
    req_body["metadata"]["labels"]["tails-app-environment"] = testenv_name
    req_body["metadata"]["labels"]["tails-app-name"] = app_template.app_name
    req_body["metadata"]["owner_references"][0]["name"] = testenv_name
    req_body["spec"]["sourceRef"]["name"] = app_template.git_repository_name
    req_body["spec"]["path"] = app_template.git_repository_path
    req_body["spec"]["postBuild"]["substitute"]["environment"] = testenv_name

    mock_api.create_namespaced_custom_object.assert_called_once_with(
        group="kustomize.toolkit.fluxcd.io",
        version="v1",
        namespace="kollie",
        plural="kustomizations",
        body=req_body,
    )


@freeze_time("2024-01-01")
@patch("kollie.cluster.kustomization_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.kustomization_request.V1OwnerReference", new=dict)
def test_create_kustomization_with_git_repository_name(mock_request_setup):
   # arrange
    testenv_name = "feature-foo"
    app_template = mock_request_setup["app_template"]
    mock_api = mock_request_setup["mock_api"]
    git_repository_name = "test-branch"

    # act
    create_kustomization(
        env_name=testenv_name,
        image_tag_prefix=app_template.default_image_tag_prefix,
        app_template=app_template,
        owner_email="test@test.local",
        owner_uid="test_uid",
        lease_exclusion_window=None,
        git_repository_name=git_repository_name,
    )

    # assert
    req_body = deepcopy(DEFAULT_REQUST_BODY)

    req_body["metadata"]["name"] = f"{testenv_name}-{app_template.app_name}"
    req_body["metadata"]["labels"]["tails-app-environment"] = testenv_name
    req_body["metadata"]["labels"]["tails-app-name"] = app_template.app_name
    req_body["metadata"]["owner_references"][0]["name"] = testenv_name
    req_body["spec"]["sourceRef"]["name"] = git_repository_name
    req_body["spec"]["sourceRef"]["namespace"] = KOLLIE_NAMESPACE
    req_body["spec"]["path"] = app_template.git_repository_path
    req_body["spec"]["postBuild"]["substitute"]["environment"] = testenv_name

    mock_api.create_namespaced_custom_object.assert_called_once_with(
        group="kustomize.toolkit.fluxcd.io",
        version="v1",
        namespace="kollie",
        plural="kustomizations",
        body=req_body,
    )


@patch("kollie.cluster.kustomization.get_kustomizations")
def test_delete_kustomization(get_kustomizations_mock, mock_kube_client):
    # arrange
    get_kustomizations_mock.return_value = [
        {"metadata": {"name": "test-kustomization"}}
    ]

    mock_api = MagicMock()
    mock_kube_client.CustomObjectsApi.return_value = mock_api
    kustomization_name = "test-kustomization"

    # act
    delete_kustomizations(kustomization_name)

    # assert
    mock_api.delete_namespaced_custom_object.assert_called_once_with(
        group="kustomize.toolkit.fluxcd.io",
        version="v1",
        plural="kustomizations",
        namespace="kollie",
        name=kustomization_name,
    )
