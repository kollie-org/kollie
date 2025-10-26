from dataclasses import asdict

from kubernetes import client
import structlog

from kollie.exceptions import KollieImagePolicyException

from .constants import KOLLIE_NAMESPACE
from .interfaces import AppTemplate
from .image_policy_spec import LatestTimestampImagePolicySpec


logger = structlog.get_logger(__name__)


def create_owned_image_policy(
    env_name: str,
    image_tag_prefix: str,
    app_template: AppTemplate,
    owner_uid: str,
    owner_kind: str = "Kustomization",
):
    """
    Creates an ImagePolicy in the kollie namespace with OwnerReferences
    so that the ImagePolicy is automatically removed when the owner is removed

    See https://kubernetes.io/docs/tasks/administer-cluster/use-cascading-deletion/

    Args:
        env_name (str): Used for labelling the ImagePolicy
        app_name (str): Used for labelling the ImagePolicy
        image_policy_spec (ImagePolicySpec): Contents of the ImagePolicy.spec
        owner_uid (str): The UID of the owner of the ImagePolicy.
            This should be the UID of the Kustomization that we need to update
            when the ImagePolicy updates.
        owner_kind (str): This should be almost always "Kustomization".

    """
    api = client.CustomObjectsApi()

    # compose common metadata for ImageRegistry and ImagePolicy resources
    # with the same owner references and labels
    owner_reference = client.V1OwnerReference(
        api_version="kustomize.toolkit.fluxcd.io/v1",
        name=f"{env_name}-{app_template.app_name}",
        block_owner_deletion=True,
        uid=owner_uid,
        kind=owner_kind,
    )

    metadata = client.V1ObjectMeta(
        name=f"{env_name}-{app_template.app_name}",
        labels={
            "tails-app-stage": "testing",
            "tails-app-environment": env_name,
            "tails-app-name": app_template.app_name,
        },
        owner_references=[owner_reference],
    )

    image_policy_spec = LatestTimestampImagePolicySpec.for_image_tag_prefix(
        app_template=app_template, image_tag_prefix=image_tag_prefix
    )

    # create the ImagePolicy resource
    image_policy = {
        "apiVersion": "image.toolkit.fluxcd.io/v1",
        "kind": "ImagePolicy",
        "metadata": metadata,
        "spec": asdict(image_policy_spec),
    }

    try:
        api.create_namespaced_custom_object(
            group="image.toolkit.fluxcd.io",
            version="v1",
            namespace=KOLLIE_NAMESPACE,
            plural="imagepolicies",
            body=image_policy,
        )
    except client.ApiException:
        logger.error(
            f"Failed to create ImagePolicy for {app_template.app_name} in {env_name}",
            app_name=app_template.app_name,
            env_name=env_name,
            image_policy=image_policy,
        )

        raise KollieImagePolicyException(
            app_name=app_template.app_name, env_name=env_name
        )


def find_image_policies(env_name: str, app_name: str | None = None):
    api = client.CustomObjectsApi()

    labels = ["tails-app-stage=testing"]
    labels.append(f"tails-app-environment={env_name}")

    if app_name is not None:
        labels.append(f"tails-app-name={app_name}")

    return api.list_namespaced_custom_object(
        group="image.toolkit.fluxcd.io",
        version="v1",
        namespace=KOLLIE_NAMESPACE,
        plural="imagepolicies",
        label_selector=",".join(labels),
    )


def delete_image_policies(env_name: str, app_name: str | None = None):
    """
    Deletes image policies related to an environment.

    """
    api = client.CustomObjectsApi()

    image_policies = find_image_policies(env_name=env_name, app_name=app_name)

    for policy in image_policies["items"]:
        api.delete_namespaced_custom_object(
            group="image.toolkit.fluxcd.io",
            version="v1",
            namespace=KOLLIE_NAMESPACE,
            plural="imagepolicies",
            name=policy["metadata"]["name"],
        )
