from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

from kubernetes.client import V1ObjectMeta, V1OwnerReference

from kollie.cluster.interfaces import AppTemplate

from .constants import KOLLIE_COMMON_SUBSTITUTIONS, KOLLIE_NAMESPACE

DEFAULT_LEASE_DAYS_EXTEND: Final[int] = 0
DEFAULT_LEASE_HOUR_EXTEND: Final[int] = 19


@dataclass
class CreateKustomizationRequest:
    """A request to create a kustomization."""

    env_name: str
    app_template: AppTemplate
    image_tag_prefix: str
    owner_email: str
    owner_uid: str
    lease_exclusion_window: str | None
    git_repository_name: str | None = None

    @property
    def kustomization_name(self) -> str:
        """Render the name of the kustomization."""
        return f"{self.env_name}-{self.app_template.app_name}"

    @property
    def uptime_window(self) -> str:
        """Render the uptime window timespan."""
        return calculate_uptime_window_string()

    @property
    def body(self) -> dict:
        """Render the body of the request."""
        if self.git_repository_name is None:
            git_repo_source_name =  self.app_template.git_repository_name
            git_repo_source_namespace =  "flux-system"
        else:
            git_repo_source_name = self.git_repository_name
            git_repo_source_namespace = KOLLIE_NAMESPACE

        return {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": V1ObjectMeta(
                name=self.kustomization_name,
                labels={
                    "tails-app-stage": "testing",
                    "tails-app-environment": self.env_name,
                    "tails-app-name": self.app_template.app_name,
                },
                annotations={
                    "tails.com/owner": self.owner_email,
                    "tails.com/tracking-image-tag-prefix": self.image_tag_prefix,
                },
                owner_references=[
                    V1OwnerReference(
                        api_version="v1",
                        name=self.env_name,
                        block_owner_deletion=True,
                        uid=self.owner_uid,
                        kind="ConfigMap",
                    ),
                ],
            ),
            "spec": {
                "path": self.app_template.git_repository_path,
                "interval": "5m",
                "sourceRef": {
                    "kind": "GitRepository",
                    "name": git_repo_source_name,
                    "namespace": git_repo_source_namespace,
                },
                "prune": True,
                "postBuild": {
                    "substitute": {
                        "environment": self.env_name,
                        "downscaler_uptime": self.lease_exclusion_window if self.lease_exclusion_window else self.uptime_window,
                    } | KOLLIE_COMMON_SUBSTITUTIONS
                },
            },
        }


@dataclass
class PatchKustomizationRequest:
    """A request to patch a kustomization."""

    env_name: str
    app_name: str
    body: dict = field(default_factory=dict)

    @property
    def kustomization_name(self) -> str:
        """Return the name of the kustomization."""
        return f"{self.env_name}-{self.app_name}"

    def set_image_tag(self, image_tag: str):
        """Set the image tag in the patch.

        Args:
            image_tag (str): The new image tag.

        Returns:
            PatchKustomizationRequest: The current instance.
        """

        self.body.setdefault("spec", {}).setdefault("postBuild", {}).setdefault(
            "substitute", {}
        )["image_tag"] = image_tag
        return self

    def set_image_tag_prefix(self, image_tag_prefix: str):
        """Set the image_tag_prefix in the patch.

        Args:
            image_tag_prefix (str): The new image_tag_prefix.

        Returns:
            PatchKustomizationRequest: The current instance.
        """
        self.body.setdefault("metadata", {}).setdefault("annotations", {})[
            "tails.com/tracking-image-tag-prefix"
        ] = image_tag_prefix
        return self

    def set_owner(self, owner_uid: str, owner_kind: str = "ConfigMap"):
        """Set the owner in the patch.

        Args:
            owner_uid (str): The uid of the owner.
            owner_kind (str): The kind of the owner.

        Returns:
            PatchKustomizationRequest: The current instance.
        """
        self.body.setdefault("metadata", {}).setdefault("ownerReferences", [{}])[0] = {
            "apiVersion": "v1",
            "name": self.env_name,
            "uid": owner_uid,
            "kind": owner_kind,
            "blockOwnerDeletion": True,
        }
        return self

    def set_uptime_window(self, uptime_window_string: str):
        """Set the lease until in the patch.

        Args:
            uptime_window_string (str): The timespan to be up.

        Returns:
            PatchKustomizationRequest: The current instance.
        """
        
        self.body.setdefault("spec", {}).setdefault("postBuild", {}).setdefault(
            "substitute", {}
        )["downscaler_uptime"] = uptime_window_string

        return self


def calculate_uptime_window_string(
    hour: int = DEFAULT_LEASE_HOUR_EXTEND,
    days: int = DEFAULT_LEASE_DAYS_EXTEND,
) -> str:
    """
    Get the uptime window timespan string.

    Leases are _always_ daily so we use the current date.

    Args:
        hour (int): The hour the lease should expire at. Valid values are between 0 and 23.
        days (int): The number of days the lease should be extended. Defaults to 0. Valid values are
        between 0 and 5

    Returns:
        str: The uptime window timespan.
    """

    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23.")

    if days < 0 or days > 5:
        raise ValueError("Days must be between 0 and 5.")

    d = datetime.now(UTC).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    now_seconds = datetime.now(UTC).replace(microsecond=0)
    return f"{now_seconds.isoformat()}-{d.isoformat()}"
