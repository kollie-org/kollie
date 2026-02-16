from kollie.cluster.ingress import get_ingress
from kollie.cluster.configmap import get_configmap
from kollie.cluster.image_policy import create_owned_image_policy, delete_image_policies
from kollie.exceptions import KollieConfigError, KollieException
from kollie.models import KollieApp, EnvironmentMetadata
from kollie.persistence import get_app_template_store
from kollie.cluster.git_repository import get_git_repository
from kollie.cluster.kustomization import (
    patch_kustomization,
    create_kustomization,
    delete_kustomizations,
    get_kustomizations,
)
from kollie.cluster.kustomization_request import PatchKustomizationRequest
import re
import os


def create_app(
    app_name: str,
    env_name: str,
    owner_email: str,
    image_tag_prefix: str | None = None,
) -> None:
    """
    Creates a new app in an environment by creating a kustomization and image policy.

    Args:
        app_name (str): The name of the app (for loading app template).
        env_name (str): The name of the environment.
        owner_email (str): The email of the owner of the environment.
        image_tag_prefix (str): Image tag prefix to run (defaults to app template default image_tag_prefix).
    """
    env_config = get_configmap(name=env_name)
    env_metadata = EnvironmentMetadata.from_configmap(env_config)

    app_templates = get_app_template_store()
    app_template = app_templates.get_by_name(app_name=app_name)

    is_remediate_image_tag = os.environ.get("KOLLIE_REMEDIATE_IMAGE_TAG", "False").lower() == "true"
    if image_tag_prefix is not None and is_remediate_image_tag:
        image_tag_prefix = re.sub(r"[^\w.-]", '-', image_tag_prefix)

    if not app_template:
        raise KollieConfigError(message=f"App template not found for {app_name}")

    env_git_repository = get_git_repository(env_name)
    git_repository_name = (
        env_git_repository["metadata"]["name"]
        if env_git_repository else None
    )

    kustomization = create_kustomization(
        env_name=env_name,
        image_tag_prefix=image_tag_prefix or app_template.default_image_tag_prefix,
        app_template=app_template,
        owner_email=owner_email,
        owner_uid=env_config.metadata.uid,
        lease_exclusion_window=env_metadata.lease_exclusion_window,
        git_repository_name=git_repository_name,
    )

    create_owned_image_policy(
        env_name=env_name,
        image_tag_prefix=image_tag_prefix or app_template.default_image_tag_prefix,
        app_template=app_template,
        owner_uid=kustomization["metadata"]["uid"],
    )


def get_app(env_name: str, app_name: str) -> KollieApp:
    """
    Returns a KollieApp for a given environment and app name.

    Args:
        env_name (str): The name of the environment.
        app_name (str): The name of the app.

    Returns:
        KollieApp: The app object.
    """
    kustomizations = get_kustomizations(env_name=env_name, app_name=app_name)

    if not kustomizations:
        raise KollieException("App not found", env_name=env_name, app_name=app_name)

    ingress = get_ingress(env_name=env_name, app_name=app_name)
    app = KollieApp.from_resources(kustomization=kustomizations[0], ingress=ingress)

    return app


def delete_app(env_name: str, app_name: str):
    """
    Deletes an app by the kustomizations and its owned resources.

    The App is deleted by deleting the Kustomization. The ImagePolicies are
    deleted by the ownerReference.

    Args:
        env_name (str): The name of the environment.
        app_name (str): The name of the app.
    """
    delete_kustomizations(env_name=env_name, app_name=app_name)


def update_app(env_name: str, app_name: str, attributes: dict[str, str]) -> None:
    """
    Updates the configuration of an app in an environment.

    Args:
        env_name (str): The name of the environment.
        app_name (str): The name of the app.
        kwargs (dict): The new configuration.

    Returns:
        None
    """
    # ensure that a kustomization for the app already exists
    app = get_app(env_name, app_name)

    if not app:
        raise KollieException("App not found", env_name=env_name, app_name=app_name)

    patch_request = PatchKustomizationRequest(env_name, app_name)

    for key, value in attributes.items():
        setter = getattr(patch_request, f"set_{key}", None)
        if callable(setter):
            setter(value)

    kustomization = patch_kustomization(patch_request)

    if "image_tag_prefix" in attributes:
        _refresh_image_policy(
            env_name=env_name,
            app_name=app_name,
            image_tag_prefix=attributes["image_tag_prefix"],
            owner_uid=kustomization["metadata"]["uid"],
        )


def _refresh_image_policy(env_name: str, app_name: str, image_tag_prefix: str, owner_uid: str):
    """
    Refreshes the image policy for an app in an environment.

    Args:
        env_name (str): The name of the environment.
        app_name (str): The name of the app.
        image_tag_prefix (str): The value of the image tag prefix.
        owner_uid (str): The UID of the owner.
    """

    app_template = get_app_template_store().get_by_name(app_name=app_name)

    if not app_template:
        raise KollieConfigError(message=f"App template not found for {app_name}")

    delete_image_policies(env_name=env_name, app_name=app_name)

    create_owned_image_policy(
        env_name=env_name,
        image_tag_prefix=image_tag_prefix,
        app_template=app_template,
        owner_uid=owner_uid,
    )
