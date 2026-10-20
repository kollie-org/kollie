
from typing import cast

import structlog
from kubernetes import client

from kollie.exceptions import KollieKustomizationException

from .constants import KOLLIE_NAMESPACE
from .interfaces import AppTemplate
from .kustomization_request import CreateKustomizationRequest, PatchKustomizationRequest

logger = structlog.get_logger(__name__)


def create_kustomization(
    env_name: str,
    image_tag_prefix: str,
    app_template: AppTemplate,
    owner_email: str,
    owner_uid: str,
    lease_exclusion_window: str | None,
    git_repository_name: str | None = None,
) -> dict:
    """Create a kustomization in the kollie namespace.

    Args:
        env_name (str): The name of the environment.
        image_tag_prefix (str): The image tag prefix to track.
        app_template (AppTemplate): The app template.
        owner_email (str): The email of the owner.
        owner_uid (str): The uid of the owner.
        lease_exclusion_window (Optional[str]): The time window where this app is immune from scale downs.
        git_repository_name (str): Optional name of non-default flux git repository.

    Returns:
        dict: The response from the API.

    Raises:
        KollieKustomizationException: If there is an error from the API.
    """
    v1 = client.CustomObjectsApi()

    request = CreateKustomizationRequest(
        env_name=env_name,
        image_tag_prefix=image_tag_prefix,
        app_template=app_template,
        owner_email=owner_email,
        owner_uid=owner_uid,
        lease_exclusion_window=lease_exclusion_window,
        git_repository_name=git_repository_name
    )

    try:
        response = cast(
            dict,
            v1.create_namespaced_custom_object(
                group="kustomize.toolkit.fluxcd.io",
                version="v1",
                namespace=KOLLIE_NAMESPACE,
                plural="kustomizations",
                body=request.body,
            ),
        )

        return response
    except client.ApiException:
        logger.error(
            f"Failed to create Kustomization for {app_template.app_name} in {env_name}",
            app_name=app_template.app_name,
            env_name=env_name,
            kustomization=request.body,
        )
        raise KollieKustomizationException(
            env_name=env_name, app_name=app_template.app_name, action="create"
        )


def patch_kustomization(request: PatchKustomizationRequest) -> dict:
    """Helper method to patch a kustomization.

    Args:
        request (PatchKustomizationRequest): The patch request.

    Returns:
        dict: The response from the API.
    """
    v1 = client.CustomObjectsApi()

    try:
        response = cast(
            dict,
            v1.patch_namespaced_custom_object(
                group="kustomize.toolkit.fluxcd.io",
                version="v1",
                namespace=KOLLIE_NAMESPACE,
                plural="kustomizations",
                name=request.kustomization_name,
                body=request.body,
            ),
        )

        return response

    except client.ApiException:
        logger.error(
            f"Failed to patch Kustomization for {request.app_name} in {request.env_name}",
            app_name=request.app_name,
            env_name=request.env_name,
            patch=request.body,
        )
        raise KollieKustomizationException(
            env_name=request.env_name, app_name=request.app_name, action="patch"
        )


def delete_kustomizations(env_name: str, app_name: str | None = None) -> None:
    """
    raises ApiException if there is an error deleting the kustomization
    """
    v1 = client.CustomObjectsApi()

    kustomizations = get_kustomizations(env_name, app_name)

    for kustomization in kustomizations:
        v1.delete_namespaced_custom_object(
            group="kustomize.toolkit.fluxcd.io",
            version="v1",
            namespace=KOLLIE_NAMESPACE,
            plural="kustomizations",
            name=kustomization["metadata"]["name"],
        )


def get_kustomizations(
    env_name: str | None = None, app_name: str | None = None
) -> list:
    """
    Returns a list of kustomizations in the "kollie" namespace,
    optionally filtered by testenv_name and app_name labels.

    Args:
        env_name (Optional[str]): The name of the test environment to filter by.
        app_name (Optional[str]): The name of the app to filter by.

    Returns:
        list: A list of kustomizations that match the given label selectors.
    """
    v1 = client.CustomObjectsApi()

    labels = ["tails-app-stage=testing"]

    if env_name:
        labels.append(f"tails-app-environment={env_name}")

    if app_name:
        labels.append(f"tails-app-name={app_name}")

    kustomizations = cast(
        dict,
        v1.list_namespaced_custom_object(
            group="kustomize.toolkit.fluxcd.io",
            version="v1",
            namespace=KOLLIE_NAMESPACE,
            plural="kustomizations",
            label_selector=",".join(labels),
        ),
    )

    return kustomizations.get("items", [])


def list_kustomizations(testenv_name: str = "", app_name: str = ""):
    kustomizations = get_kustomizations(testenv_name, app_name)

    kustomization_list = []
    for kustomization in kustomizations:
        name = kustomization["metadata"]["name"]
        kustomization_list.append(name)
    return kustomization_list
