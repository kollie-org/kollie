import datetime
import json
from typing import List
from unittest.mock import Mock

from kubernetes.client.models.v1_config_map import V1ConfigMap

from kollie.persistence.app_template import AppTemplate, ImageRepositoryRef


def build_kustomization(env_name: str, app_name: str) -> dict:
    return {
        "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
        "kind": "Kustomization",
        "metadata": {
            "creationTimestamp": "2023-09-21T12:46:31Z",
            "finalizers": ["finalizers.fluxcd.io"],
            "generation": 1,
            "labels": {
                "tails-app-environment": env_name,
                "tails-app-name": app_name,
                "tails-app-stage": "testing",
            },
            "managedFields": [],
            "name": f"{env_name}-{app_name}",
            "namespace": "kollie",
            "annotations": {},
        },
        "status": {
            "conditions": [
                {
                    "lastTransitionTime": "2023-09-28T14:10:41Z",
                    "message": "Applied revision: staging@sha1:shashashasha",
                    "observedGeneration": 1,
                    "reason": "ReconciliationSucceeded",
                    "status": "True",
                    "type": "Ready",
                }
            ],
            "inventory": {
                "entries": [
                    {"id": f"_{app_name}-{env_name}__Namespace", "v": "v1"},
                    {
                        "id": f"{app_name}-{env_name}_helm.toolkit.fluxcd.io_HelmRelease",  # noqa
                        "v": "v2",
                    },
                    {
                        "id": f"{app_name}-{env_name}_image.toolkit.fluxcd.io_ImagePolicy",  # noqa
                        "v": "v1",
                    },
                    {
                        "id": f"{app_name}-{env_name}_image.toolkit.fluxcd.io_ImageRepository",  # noqa
                        "v": "v1",
                    },
                ]
            },
            "lastAppliedRevision": "staging@sha1:shashashasha",
            "lastAttemptedRevision": "staging@sha1:shashashasha",
            "observedGeneration": 1,
        },
        "spec": {
            "force": False,
            "interval": "5m",
            "path": f"./{app_name}/testing",
            "postBuild": {"substitute": {"environment": env_name}},
            "prune": True,
            "sourceRef": {
                "kind": "GitRepository",
                "name": "test-repo",
                "namespace": "flux-system",
            },
        },
    }


def build_configmaps(environments: List[dict]) -> List[Mock]:
    items = []
    for environment in environments:
        configmap = Mock(spec=V1ConfigMap)
        configmap.api_version = "v1"
        configmap.kind = "ConfigMap"
        configmap.data = {
            "json": json.dumps(
                {
                    "env_name": environment["name"],
                    "created_at": datetime.datetime.now(datetime.UTC).strftime(
                        "%d-%m-%Y %H:%M:%S"
                    ),
                    "lease_exclusion_window": environment["lease_exclusion_window"] if "lease_exclusion_window" in environment else None
                }
            )
        }
        metadata = Mock()
        metadata.name = environment["name"]
        metadata.annotations = {"tails.com/owner": environment["owner_email"]}
        metadata.labels = {
            "tails-app-stage": "testing",
            "tails-app-environment": environment["name"],
            "kollie.tails.com/managed-by": "kollie",
        }
        metadata.namespace = "kollie"

        configmap.metadata = metadata

        items.append(configmap)

    return items


class MagicAppTemplateSource:
    """
    This class implements the AppTemplateSource protocol for testing purposes.
    It autogenerates AppTemplates for a list of app names given as init argument.
    """

    def __init__(self, app_names: list[str]) -> None:
        self._app_names = app_names

    def load(self) -> list[AppTemplate]:
        return [
            AppTemplate(
                app_name=app_name,
                label=f"{app_name}_label",
                git_repository_name="test-flux-repo",
                git_repository_path="bob/builder",
                image_repository_ref=ImageRepositoryRef(
                    name=f"{app_name}_repo", namespace=f"{app_name}_namespace"
                ),
                default_image_tag_prefix="main",
            )
            for app_name in self._app_names
        ]
