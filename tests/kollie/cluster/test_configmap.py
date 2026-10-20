from unittest.mock import patch

import pytest
from freezegun import freeze_time

from kollie.cluster.configmap import (
    create_env_configmap,
    delete_configmap,
    get_configmap,
    get_configmaps,
)


@pytest.fixture(autouse=True)
def mock_api():
    with patch("kollie.cluster.configmap.client.CoreV1Api") as mock_api:
        yield mock_api


def test_get_configmap(mock_api):
    mock_instance = mock_api.return_value
    get_configmap("test-configmap", "test-namespace")

    mock_instance.read_namespaced_config_map.assert_called_once_with(
        "test-configmap", "test-namespace"
    )


def test_get_configmaps(mock_api):
    mock_instance = mock_api.return_value
    get_configmaps(label_filters={"test": "test"})

    mock_instance.list_namespaced_config_map.assert_called_once_with(
        "kollie", label_selector="tails-app-stage=testing,test=test"
    )


@freeze_time("2024-01-19 15:03:08")
@patch("kollie.cluster.configmap.client.V1ConfigMap", new=dict)
@patch("kollie.cluster.configmap.client.V1ObjectMeta", new=dict)
def test_create_env_configmap(mock_api):
    mock_instance = mock_api.return_value
    create_env_configmap(
        env_name="test-configmap",
        apps=["test-app1", "test-app2"],
        owner_email="test@testing.com",
        lease_exclusion_window="Mon-Fri 07:00-19:00 Europe/London",
    )

    mock_instance.create_namespaced_config_map.assert_called_once_with(
        "kollie",
        {
            "api_version": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "test-configmap",
                "annotations": {
                    "kollie.tails.com/created-at": "2024-01-19T15:03:08",
                    "tails.com/owner": "test@testing.com",
                },
                "labels": {
                    "tails-app-stage": "testing",
                    "tails-app-environment": "test-configmap",
                    "kollie.tails.com/managed-by": "kollie",
                },
            },
            "data": {
                "json": '{"env_name": "test-configmap", "created_at": "2024-01-19T15:03:08", "apps": ["test-app1", "test-app2"], "lease_exclusion_window": "Mon-Fri 07:00-19:00 Europe/London"}'
            },
        },
    )


def test_delete_configmap(mock_api):
    mock_instance = mock_api.return_value

    delete_configmap("test-configmap", "test-namespace")
    mock_instance.delete_namespaced_config_map.assert_called_once_with(
        "test-configmap", "test-namespace"
    )
