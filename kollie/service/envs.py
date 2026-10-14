
import structlog
from environs import Env

from kollie.cluster.configmap import (
    create_env_configmap,
    delete_configmap,
    get_configmap,
    get_configmaps,
)
from kollie.cluster.git_repository import (
    create_git_repository,
    get_git_repository,
)
from kollie.cluster.kustomization import (
    get_kustomizations,
)
from kollie.cluster.kustomization_request import calculate_uptime_window_string
from kollie.exceptions import KollieConfigError
from kollie.models import EnvironmentMetadata, KollieEnvironment
from kollie.persistence import get_app_template_store
from kollie.persistence.app_bundle import AppBundle, get_app_bundle_store
from kollie.service.applications import create_app, update_app

env = Env()

EXTENDED_LEASE_TEST_ENV_NAMES: list[str] = env.list("KOLLIE_EXTENDED_LEASE_TEST_ENV_NAMES", [])
ENV_NAME_LABEL = "tails-app-environment"


logger = structlog.get_logger(__name__)


def list_envs(owner_email: str | None = None) -> list[EnvironmentMetadata]:
    """
    Get a list of environment names stored in configmaps.

    Returns:
        List[str]: A list of environment names.
    """
    label_filters = {"kollie.tails.com/managed-by": "kollie"}

    env_configmaps = get_configmaps(label_filters=label_filters)

    envs = []

    for env_configmap in env_configmaps:

        if not env_configmap.data or env_configmap.metadata is None:
            continue

        # This is an inefficient way to filter by owner. It is done this way
        # because it's not possible to filter by annotation in Kubernetes
        # We are using annotations for the owner email because labels don't
        # support the @ symbol
        if (
            owner_email is not None
            and env_configmap.metadata.annotations["tails.com/owner"] != owner_email
        ):
            continue

        metadata = EnvironmentMetadata.from_configmap(env_configmap)

        envs.append(metadata)

    envs = sorted(envs, key=lambda env: env.name)

    return envs


def get_env(env_name: str) -> KollieEnvironment | None:
    """
    Returns a KollieEnvironment for a given environment name.

    Args:
        env_name (str): The name of the environment.

    Returns:
        KollieEnvironment: The environment object.
    """
    env_config = get_configmap(name=env_name)

    owner_email = env_config.metadata.annotations.get("tails.com/owner")

    git_repository = get_git_repository(env_name)
    flux_repository_branch = (
        git_repository["spec"]["ref"]["branch"] if git_repository else None
    )

    kustomizations = get_kustomizations(env_name=env_name)

    env = KollieEnvironment.from_kustomizations(
        env_name=env_name,
        kustomizations=kustomizations,
        owner_email=owner_email,
        flux_repository_branch=flux_repository_branch,
    )

    return env


def get_available_apps(env: KollieEnvironment) -> list[str]:
    """
    Returns a list of apps that can be added to an environment.

    Args:
        env (KollieEnvironment): The environment object.

    Returns:
        List[str]: A list of app names.
    """
    app_templates = get_app_template_store()
    all_templates = app_templates.get_all()

    available_apps = [
        template.app_name
        for template in all_templates
        if template.app_name not in env.app_names
    ]

    return available_apps


def create_env(
    env_name: str, owner_email: str, flux_repo_branch: str | None = None
) -> None:
    """
    Creates a new environment by creating a kustomization for each app.

    Args:
        env_name (str): The name of the environment.
        owner_email (str): The email of the owner of the environment.
        flux_repo_branch (str): Optional k8s-apps branch to use for environment.
    """
    lease_exclusion_list: list[str] = env.list("KOLLIE_LEASE_EXCLUSION_LIST", [])
    lease_exclusion_window = None
    if lease_exclusion_list and env_name in lease_exclusion_list:
        lease_exclusion_window = "Mon-Fri 07:00-19:00 Europe/London"
    env_config = create_env_configmap(
        env_name=env_name,
        owner_email=owner_email,
        lease_exclusion_window=lease_exclusion_window,
    )

    if flux_repo_branch:
        owner_uid = env_config.metadata.uid
        create_git_repository(
            env_name=env_name,
            branch=flux_repo_branch,
            owner_email=owner_email,
            owner_uid=owner_uid
        )


def extend_lease(env_name: str, hour: int, days: int = 0):
    """
    Extends the uptime of an environment by setting the downscaler/uptime
    annotation for each kustomization in the environment.

    Args:
        env_name (str): The name of the environment to extend the lease for.
        hour (int): The hour the lease should expire at. Valid values are between 0 and 23.
        days (int): The number of days the lease should be extended. Defaults to 0.
    """
    env = get_env(env_name)

    if not env:
        raise ValueError(f"Environment {env_name} not found.")

    for app in env.apps:
        update_app(
            app_name=app.name,
            env_name=env_name,
            attributes={"uptime_window": calculate_uptime_window_string(hour=hour, days=days)},
        )

    # store the uptime_window_string in the configmap for quick reference


def delete_env(env_name: str):
    """
    Deletes an environment by the configmap and its owned resources.

    The Environment is deleted by deleting the configmap. The Kustomizations
    and ImagePolicies are deleted by the ownerReference.

    Args:
        env_name (str): The name of the environment.
    """
    delete_configmap(name=env_name)


def get_available_app_bundles(env_name: str) -> list[AppBundle]:
    # TODO: Do we need to filter out bundles already deployed? How?
    return get_app_bundle_store().get_all_bundles()


def install_bundle(env_name: str, bundle_name: str, owner_email: str):
    """
    Deploys a bundle of apps to an environment, using the default branch
    for each app defined in app template.

    Args:
        env_name (str): The name of the environment.
        bundle_name (str): The name of the bundle.
    """
    bundle = get_app_bundle_store().get_bundle(name=bundle_name)
    template_store = get_app_template_store()

    if not bundle:
        raise KollieConfigError(message=f"Bundle not found for {bundle_name}")

    environment = get_env(env_name=env_name)

    if not environment:
        raise KollieConfigError(message=f"Environment not found for {env_name}")

    # Check there are templates for all the apps in the bundle _before_ we create
    # any apps. This way we don't end up with dangling apps in the cluster.
    for bundle_app in bundle.apps:
        if not template_store.get_by_name(bundle_app):
            raise KollieConfigError(message=f"App template not found for {bundle_app}")

    for bundle_app in bundle.apps:
        if bundle_app not in environment.app_names:
            template = template_store.get_by_name(bundle_app)

            # We already checked for this above but mypy doesn't know that.
            # Leaving this check here rather than silencing mypy.
            if not template:
                raise KollieConfigError(
                    message=f"App template not found for {bundle_app}"
                )

            create_app(
                app_name=template.app_name,
                env_name=env_name,
                owner_email=owner_email,
                image_tag_prefix=template.default_image_tag_prefix,
            )
            logger.debug("app.deployed", app_name=bundle_app, env_name=env_name)

        else:
            logger.debug("app.already_deployed", app_name=bundle_app, env_name=env_name)
