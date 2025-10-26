"""
Design:
  - When creating a Kustomization, we also publish a ImagePolicy CRD in kollie namespace
    to watch for a pattern like '^{branch-name}-[a-fA-F0-9]+-(?P<ts>.*)'.
        - Tag/Label the ImagePolicy with the Kustomization (vice versa)
        - DECISION NEEDED: How do we know imageRepositoryRef and other necessary
          information for the ImagePolicy?

  - We monitor all the ImagePolicy resources that we created for updates
  - We update the Kustomization with the latest image tag when the corresponding
    ImagePolicy updates

"""

# Path: kollie/cluster/image_update_automation.py
from kollie.cluster.constants import KOLLIE_NAMESPACE
from kubernetes import client, watch
import structlog
from kollie.cluster.image_policy import find_image_policies

from kollie.service import applications


logger = structlog.get_logger(__name__)


def watch_for_image_updates():
    """
    entrypoint for binaries to call.
    Procedure:
        - Collect a list of ImagePolicy resources that we want to watch
        - Watch for ImagePolicy events.
        - Trigger an update to Kustomization for each event (if eligible)
    """
    api = client.CustomObjectsApi()

    _w = watch.Watch()
    filters = dict(
        group="image.toolkit.fluxcd.io",
        version="v1",
        namespace=KOLLIE_NAMESPACE,
        plural="imagepolicies",
    )

    try:
        for event in _w.stream(api.list_namespaced_custom_object, **filters):
            try:
                handle_image_policy_event(event)
            except client.ApiException as e:
                logger.error(
                    "image_update_automation.failed",
                    error_status=e.status,
                    error_reason=e.reason,
                    headers=e.headers,
                    body=e.body,
                )
                continue

            except Exception as e:
                logger.error(
                    "image_update_automation.failed", error=e, image_policy_event=event
                )
                continue

    except (SystemExit, KeyboardInterrupt):
        logger.info("Graceful shutdown initiated")


def _extract_env_name(event) -> str | None:
    """
    Extracts the environment name from the event labels.

    Args:
        event (dict): The event to extract labels from.

    Returns:
        str: The environment name.
    """
    try:
        labels = event["object"]["metadata"]["labels"]
        env_name = labels["tails-app-environment"]
        return env_name
    except KeyError:
        logger.warning("skipping unlabelled image update policy", image_policy_event=event)
        return None


def _extract_app_name(event) -> str | None:
    """
    Extracts the app name from the event labels.

    Args:
        event (dict): The event to extract labels from.

    Returns:
        str: The app name.
    """
    try:
        labels = event["object"]["metadata"]["labels"]
        app_name = labels["tails-app-name"]
        return app_name
    except KeyError:
        logger.warning("skipping unlabelled image update policy", image_policy_event=event)
        return None


def _get_latest_image(image_policies) -> str | None:
    """
    Gets the latest image from the image policies.

    Args:
        image_policies (dict): The image policies to get the latest image from.

    Returns:
        str: The latest image.
    """
    if not image_policies["items"]:
        return None

    image_policy = image_policies["items"][0]

    try:
        return image_policy["status"]["latestRef"]["tag"]
    except KeyError:
        logger.warning("skip.latestRef_not_found", image_policy=image_policy)
        return None


def handle_image_policy_event(event) -> None:
    """
    This method is responsible for handling image policy events.
    It updates the image tag for the relevant app by patching the appropriate
    kustomization's custom_image_tag (postBuild variable substitution).

    Args:
        event (dict): The event to be handled.

    Returns:
        None
    """
    env_name = _extract_env_name(event)
    app_name = _extract_app_name(event)

    if env_name is None or app_name is None:
        return

    image_policies = find_image_policies(env_name=env_name, app_name=app_name)

    if not image_policies["items"]:
        logger.warning(
            "No image policy found for event",
            app_name=app_name,
            env_name=env_name,
            event_data=event,
        )
        return

    latest_image_tag = _get_latest_image(image_policies)

    if latest_image_tag is None:
        return

    applications.update_app(
        env_name=env_name, app_name=app_name, attributes={"image_tag": latest_image_tag}
    )

    logger.info(
        "image_update_automation.complete",
        env_name=env_name,
        app_name=app_name,
        image_tag=latest_image_tag,
    )
