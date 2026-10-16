from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time

from kollie.cluster.constants import KOLLIE_NAMESPACE
from kollie.cluster.kustomization_request import (
    DEFAULT_LEASE_DAYS_EXTEND,
    DEFAULT_LEASE_HOUR_EXTEND,
    CreateKustomizationRequest,
    PatchKustomizationRequest,
    calculate_uptime_window_string,
)


@freeze_time("2024-01-01")
@patch("kollie.cluster.kustomization_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.kustomization_request.V1OwnerReference", new=dict)
def test_kustomization_request_body():
    env_name = "test_env"
    image_tag_prefix = "test_image_tag_prefix"
    app_template = Mock(
        app_name="test_app",
        git_repository_path="test_path",
        git_repository_name="test_name",
    )
    owner_email = "test@owner.com"
    owner_uid = "test_uid"

    request = CreateKustomizationRequest(
        env_name=env_name,
        app_template=app_template,
        image_tag_prefix=image_tag_prefix,
        owner_email=owner_email,
        owner_uid=owner_uid,
        lease_exclusion_window=None,
    )

    assert request.body == {
        "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
        "kind": "Kustomization",
        "metadata": {
            "name": f"{env_name}-{app_template.app_name}",
            "labels": {
                "tails-app-stage": "testing",
                "tails-app-environment": env_name,
                "tails-app-name": app_template.app_name,
            },
            "annotations": {
                "tails.com/owner": owner_email,
                "tails.com/tracking-image-tag-prefix": image_tag_prefix,
            },
            "owner_references": [
                {
                    "api_version": "v1",
                    "kind": "ConfigMap",
                    "name": "test_env",
                    "uid": "test_uid",
                    "block_owner_deletion": True,
                }
            ],
        },
        "spec": {
            "interval": "5m",
            "sourceRef": {
                "kind": "GitRepository",
                "name": app_template.git_repository_name,
                "namespace": "flux-system",
            },
            "prune": True,
            "path": app_template.git_repository_path,
            "postBuild": {
                "substitute": {
                    "environment": env_name,
                    "aws_account": "1234",
                    "ecr_mirror": "5678",
                    "stage": "testing",
                    "zone_name": "testenvs.example.com",
                    "downscaler_uptime": "2024-01-01T00:00:00+00:00-2024-01-01T19:00:00+00:00",
                }
            },
        },
    }


@freeze_time("2024-01-01")
@patch("kollie.cluster.kustomization_request.V1ObjectMeta", new=dict)
@patch("kollie.cluster.kustomization_request.V1OwnerReference", new=dict)
def test_kustomization_request_body_with_flux_repository_branch():
    env_name = "test_env"
    image_tag_prefix = "test_image_tag_prefix"
    app_template = Mock(
        app_name="test_app",
        git_repository_path="test_path",
        git_repository_name="test_name",
    )
    owner_email = "test@owner.com"
    owner_uid = "test_uid"
    git_repository_name = "test-git-repo"

    request = CreateKustomizationRequest(
        env_name=env_name,
        app_template=app_template,
        image_tag_prefix=image_tag_prefix,
        owner_email=owner_email,
        owner_uid=owner_uid,
        lease_exclusion_window=None,
        git_repository_name=git_repository_name,
    )

    assert request.body["spec"]["sourceRef"] == {
        "kind": "GitRepository",
        "name": git_repository_name,
        "namespace": KOLLIE_NAMESPACE,
    }


def test_kustomization_name():
    request = PatchKustomizationRequest("env", "app")
    assert request.kustomization_name == "env-app"


def test_set_image_tag():
    request = PatchKustomizationRequest("env", "app")
    request.set_image_tag("new_image_tag")
    assert (
        request.body["spec"]["postBuild"]["substitute"]["image_tag"] == "new_image_tag"
    )


def test_set_image_tag_prefix():
    request = PatchKustomizationRequest("env", "app")
    request.set_image_tag_prefix("new_image_tag_prefix")
    assert (
        request.body["metadata"]["annotations"]["tails.com/tracking-image-tag-prefix"]
        == "new_image_tag_prefix"
    )


def test_set_owner():
    request = PatchKustomizationRequest("env", "app")
    request.set_owner("new_owner_uid")
    owner_ref = request.body["metadata"]["ownerReferences"][0]
    assert owner_ref["apiVersion"] == "v1"
    assert owner_ref["name"] == "env"
    assert owner_ref["uid"] == "new_owner_uid"
    assert owner_ref["kind"] == "ConfigMap"
    assert owner_ref["blockOwnerDeletion"] is True


def test_all_setters():
    request = PatchKustomizationRequest("env", "app")
    request.set_image_tag("new_image_tag")
    request.set_image_tag_prefix("new_image_tag_prefix")
    request.set_owner("new_owner_uid")

    expected_body = {
        "spec": {"postBuild": {"substitute": {"image_tag": "new_image_tag"}}},
        "metadata": {
            "annotations": {"tails.com/tracking-image-tag-prefix": "new_image_tag_prefix"},
            "ownerReferences": [
                {
                    "apiVersion": "v1",
                    "name": "env",
                    "uid": "new_owner_uid",
                    "kind": "ConfigMap",
                    "blockOwnerDeletion": True,
                }
            ],
        },
    }

    assert request.body == expected_body


@freeze_time("2024-12-24")
def test_calculate_uptime_window_default_parameters():
    delta = timedelta(days=DEFAULT_LEASE_DAYS_EXTEND, hours=DEFAULT_LEASE_HOUR_EXTEND)
    expected_time = (datetime.now(UTC).replace(microsecond=0) + delta).isoformat()
    assert calculate_uptime_window_string()[-25:] == expected_time

@freeze_time("2024-12-24")
@pytest.mark.parametrize(
    "hour, days, expected_time",
    [
        (15, 2, "2024-12-26T15:00:00+00:00"),
        (0, 0, "2024-12-24T00:00:00+00:00"),
        (23, 1, "2024-12-25T23:00:00+00:00"),
        (12, 5, "2024-12-29T12:00:00+00:00"),
        (8, 3, "2024-12-27T08:00:00+00:00"),
    ],
)
def test_calculate_uptime_window_values(hour: int, days: int, expected_time: str):
    assert calculate_uptime_window_string(hour=hour, days=days)[-25:] == expected_time


@pytest.mark.parametrize("hour", [-1, 24, 30])
def test_calculate_uptime_window_invalid_hour(hour):
    with pytest.raises(ValueError, match="Hour must be between 0 and 23."):
        calculate_uptime_window_string(hour=hour)


@pytest.mark.parametrize("days", [-1, 6, 20])
def test_calculate_uptime_window_invalid_days(days):
    with pytest.raises(ValueError, match="Days must be between 0 and 5."):
        calculate_uptime_window_string(days=days)
