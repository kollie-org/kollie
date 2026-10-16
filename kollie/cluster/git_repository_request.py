from dataclasses import dataclass

from kubernetes.client import V1ObjectMeta, V1OwnerReference

from .constants import DEFAULT_FLUX_REPOSITORY, KOLLIE_NAMESPACE


@dataclass
class CreateGitRepositoryRequest:
    """A request to create a git repository."""

    env_name: str
    branch: str
    owner_email: str
    owner_uid: str
    git_repository_name: str

    @property
    def body(self) -> dict:
        """Render the body of the request."""
        return {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": V1ObjectMeta(
                name=self.git_repository_name,
                namespace=KOLLIE_NAMESPACE,
                labels={
                    "tails-app-stage": "testing",
                    "tails-app-environment": self.env_name,
                },
                annotations={
                    "tails.com/owner": self.owner_email,
                    "tails.com/tracking-branch": self.branch,
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
                "interval": "5m",
                "ref": {"branch": self.branch},
                "secretRef": {"name": DEFAULT_FLUX_REPOSITORY},
                "url": f"ssh://git@github.com/tailsdotcom/{DEFAULT_FLUX_REPOSITORY}",
            },
        }
