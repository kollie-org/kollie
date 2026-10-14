
from kubernetes import client


def get_ingress(env_name: str, app_name: str) -> client.V1IngressList | None:
    """
    Get an ingress from the cluster with specific labels.

    You will notice that the namespace is defaulted to the env_name.
    The reason for this is that in Kollie each environment has its own namespace.

    Args:
        env_name (str): Value for the 'env' label
        app_name (str): Value for the 'app' label
    """

    api = client.NetworkingV1Api()
    label_selector = f"tails-environment={env_name},tails-app-name={app_name}"

    ingresses = api.list_ingress_for_all_namespaces(label_selector=label_selector)

    if ingresses.items:
        return ingresses.items[0]

    return None
