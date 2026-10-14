import datetime
import json

from kubernetes import client
from kubernetes.client.models.v1_config_map import V1ConfigMap

from kollie.cluster.kustomization import KOLLIE_NAMESPACE


def get_configmap(name: str, namespace: str = ""):
    """
    Get a configmap from the cluster.

    Args:
        name (str): Name of the configmap
        namespace (str): Namespace of the configmap

    Returns:
        V1ConfigMap: The configmap
    """
    try:
        v1 = client.CoreV1Api()
        return v1.read_namespaced_config_map(name, namespace or KOLLIE_NAMESPACE)
    except client.ApiException as exc:
        if exc.status == 404:
            return None
        raise exc


def get_configmaps(label_filters: dict[str, str] | None = None) -> list[V1ConfigMap]:
    """
    Get a list of configmaps from the cluster.

    Args:
        label_filters (dict[str, str]): Label filters to apply

    Returns:
        List[V1ConfigMap]: A list of configmaps
    """
    v1 = client.CoreV1Api()

    label_filters = label_filters or {}
    labels = ["tails-app-stage=testing"]

    for key, value in label_filters.items():
        labels.append(f"{key}={value}")

    configmaps = v1.list_namespaced_config_map(
        KOLLIE_NAMESPACE, label_selector=",".join(labels)
    )

    return configmaps.items


def create_env_configmap(
    env_name: str,
    owner_email: str,
    lease_exclusion_window: str | None,
    apps: list[str] | None = None,
):
    """
    Create a configmap in the cluster.

    Args:
        env_name (str): Name of the environment
        owner_email (str): Email of the owner
        apps (List[str]): List of apps to add to the configmap
        lease_exclusion_window (str): String to pass for downscaler default uptime

    Returns:
        V1ConfigMap: The created configmap
    """
    v1 = client.CoreV1Api()

    created_at = datetime.datetime.now().isoformat()

    metadata = client.V1ObjectMeta(
        name=env_name,
        annotations={
            "kollie.tails.com/created-at": created_at,
            "tails.com/owner": owner_email,
        },
        labels={
            "tails-app-stage": "testing",
            "tails-app-environment": env_name,
            "kollie.tails.com/managed-by": "kollie",
        },
    )

    data = {
        "env_name": env_name,
        "created_at": created_at,
        "apps": apps or [],
    }

    if lease_exclusion_window:
        data["lease_exclusion_window"] = lease_exclusion_window

    body = client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        metadata=metadata,
        data={"json": json.dumps(data)},
    )

    return v1.create_namespaced_config_map(KOLLIE_NAMESPACE, body)


def delete_configmap(name, namespace=None):
    """
    Delete a configmap from the cluster.

    Args:
        name (str): Name of the configmap
        namespace (str): Namespace of the configmap

    Returns:
        V1Status: The status of the delete operation
    """
    v1 = client.CoreV1Api()
    return v1.delete_namespaced_config_map(name, namespace or KOLLIE_NAMESPACE)
