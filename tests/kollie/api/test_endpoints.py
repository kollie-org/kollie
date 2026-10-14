import json
import os
from unittest.mock import mock_open, patch

from freezegun import freeze_time
from kubernetes.client.models import V1ConfigMap, V1ObjectMeta

from kollie.models import KollieEnvironment
from tests.kollie.helpers import build_configmaps, build_kustomization


def test_ping(test_client):
    response = test_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "Pong..."}


@patch("builtins.open", new_callable=mock_open)
@patch.dict(os.environ, {"KOLLIE_APP_TEMPLATE_JSON_PATH": "dummy_path"})
def test_apps(mock_open_func, test_client):
    app_templates = [
        {
            "app_name": "test_app",
            "label": "test_label",
            "git_repository_name": "flux-test-repo",
            "git_repository_path": "bob/builder",
            "image_repository_ref": {
                "name": "test_repo",
                "namespace": "test_namespace",
            },
            "default_image_tag_prefix": "main",
        },
        {
            "app_name": "test_app_2",
            "label": "test_label_2",
            "git_repository_name": "flux-test-repo-2",
            "git_repository_path": "bob/builder",
            "image_repository_ref": {
                "name": "test_repo_2",
                "namespace": "test_namespace_2",
            },
            "default_image_tag_prefix": "main",
        },
    ]

    mock_open_func.return_value.read.return_value = json.dumps(app_templates)

    response = test_client.get("/api/apps")

    assert response.status_code == 200
    assert response.json() == app_templates


@freeze_time("2024-01-01")
@patch("kollie.service.envs.get_configmaps")
def test_environment_index(get_configmaps_mock, test_client):
    get_configmaps_mock.return_value = build_configmaps(
        environments=[
            {
                "name": "env1",
                "owner_email": "test@owner.com",
            },
            {
                "name": "env2",
                "lease_exclusion_window": "stuff and things",
                "owner_email": "test2@owner.com",
            },
        ]
    )

    response = test_client.get("/api/env")

    assert response.status_code == 200

    assert response.json() == [
        {
            "name": "env1",
            "owner_email": "test@owner.com",
            "lease_exclusion_window": None,
            "created_at": "2024-01-01T00:00:00",
        },
        {
            "name": "env2",
            "owner_email": "test2@owner.com",
            "created_at": "2024-01-01T00:00:00",
            "lease_exclusion_window": "stuff and things",
        },
    ]


@patch("kollie.service.envs.get_kustomizations", autospec=True)
@patch("kollie.service.envs.get_configmap", autospec=True)
@patch("kollie.service.envs.get_git_repository", autospec=True)
def test_environment_details(
    get_git_repository_mock ,get_configmap_mock, get_kustomizations_mock,
    test_client
):
    # arrange
    get_kustomizations_mock.return_value = [
        build_kustomization(env_name="hounslow", app_name="AlladinsFriedChicken"),
        build_kustomization(env_name="hounslow", app_name="SKVP"),
    ]

    get_configmap_mock.return_value = V1ConfigMap(
        metadata=V1ObjectMeta(annotations={"tails.com/owner": "dnshio"})
    )

    get_git_repository_mock.return_value = {
        "apiVersion": "source.toolkit.fluxcd.io/v1",
        "kind": "GitRepository",
        "metadata": {
            "name": "test-repo-hounslow",
        },
        "spec": {
            "ref": {
                "branch": "feat-catalogue-kollie"
            },
        },
    }

    # act
    response = test_client.get("/api/env/hounslow")

    # assert
    assert response.status_code == 200

    response_body = response.json()

    assert response_body["name"] == "hounslow"

    actual_app_names = [app["name"] for app in response_body["apps"]]
    assert not set(actual_app_names) ^ set(["AlladinsFriedChicken", "SKVP"])


@patch("kollie.service.envs.create_env", autospec=True)
@patch("kollie.service.envs.get_env", autospec=True)
def test_create_environment(get_env_mock, create_env_mock, test_client):
    # we are patching at the service level for this endpoint and rely on
    # separate tests for ensuring the service methods behave as expected

    get_env_mock.return_value = KollieEnvironment(
        name="env1",
        apps=[],
        owner_email="test@test.local",
        flux_repository_branch="test-branch"
    )

    # act
    response = test_client.post(
        "/api/env",
        json={"env_name": "env1", "flux_repo_branch": "test-branch"},
        headers={"X-AUTH-REQUEST-EMAIL": "test@test.local"},
    )

    # assert
    assert response.status_code == 201
    create_env_mock.assert_called_once_with(
        env_name="env1",
        owner_email="test@test.local",
        flux_repo_branch="test-branch"
    )
    assert response.json() == {
        "name": "env1",
        "apps": [],
        "owner_email": "test@test.local",
        "flux_repository_branch": "test-branch",
        "created_on": None,
    }
