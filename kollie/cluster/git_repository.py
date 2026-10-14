import structlog
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from kollie.exceptions import (
    CreateCustomObjectsApiException,
    GetCustomObjectsApiException,
)

from .constants import DEFAULT_FLUX_REPOSITORY, KOLLIE_NAMESPACE
from .git_repository_request import CreateGitRepositoryRequest

logger = structlog.get_logger(__name__)

GROUP = "source.toolkit.fluxcd.io"
VERSION = "v1"
OBJECT_PLURAL = "gitrepositories"


def git_repository_name(env_name: str) -> str:
    """Render the name of the flux git repository."""
    return f"{DEFAULT_FLUX_REPOSITORY}-{env_name}"


def create_git_repository(
    env_name: str,
    branch: str,
    owner_email: str,
    owner_uid: str,
) -> dict:
    """Create a flux git repository in the kollie namespace."""
    request = CreateGitRepositoryRequest(
        env_name=env_name,
        branch=branch,
        owner_email=owner_email,
        owner_uid=owner_uid,
        git_repository_name=git_repository_name(env_name)
    )

    custom_object_api = client.CustomObjectsApi()
    try:
        response = custom_object_api.create_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=KOLLIE_NAMESPACE,
            plural=OBJECT_PLURAL,
            body=request.body,
        )

        return response
    except ApiException as api_exc:
        logger.error(
            f"Failed to create namespaced custom object: {OBJECT_PLURAL}",
        )
        raise CreateCustomObjectsApiException(
            custom_object=OBJECT_PLURAL,
            request_body=request.body
        ) from api_exc


def get_git_repository(env_name: str) -> dict | None:
    """Return custom git repository object if exists for env."""
    name = git_repository_name(env_name=env_name)
    custom_object_api = client.CustomObjectsApi()

    try:
        return custom_object_api.get_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=KOLLIE_NAMESPACE,
            plural=OBJECT_PLURAL,
            name=name,
        )
    except ApiException as api_exc:
        if api_exc.status == 404:
            return None
        else:
            logger.error(
                f"Failed to get namespaced {OBJECT_PLURAL} custom object: {name}"
            )
            raise GetCustomObjectsApiException(
                name=name, custom_object=OBJECT_PLURAL
            ) from api_exc
