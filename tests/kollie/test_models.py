import pytest
from kubernetes.client.models.v1_ingress import V1Ingress

from kollie.models import KollieApp, KollieAppEvent, KollieEnvironment


@pytest.fixture
def kustomization():
    return {
        "metadata": {
            "annotations": {"tails.com/tracking-image-tag-prefix": "TestBranch"},
            "labels": {
                "tails-app-name": "TestApp",
                "tails-app-environment": "TestEnv",
            },
        },
        "spec": {
            "postBuild": {"substitute": {"image_tag": "TestImageTag"}},
        },
        "status": {
            "conditions": [
                {
                    "status": "True",
                    "type": "Reconciling",
                    "reason": "TestReason",
                    "message": "TestMessage",
                },
            ],
        },
    }


def test_kollie_app_event_from_condition():
    condition = {
        "status": "True",
        "type": "Reconciling",
        "reason": "TestReason",
        "message": "TestMessage",
    }
    event = KollieAppEvent.from_condition(condition)
    assert event.ready is True
    assert event.status_reason == "TestReason"
    assert event.status_message == "TestMessage"


def test_kollie_app_from_resources(mocker, kustomization):

    ingress = mocker.MagicMock(spec=V1Ingress)
    ingress.spec = mocker.MagicMock(
        rules=[
            mocker.MagicMock(
                host="TestHost",
                http=mocker.MagicMock(paths=[mocker.MagicMock(path="/TestPath")]),
            )
        ]
    )

    app = KollieApp.from_resources(kustomization, ingress)

    assert app.name == "TestApp"
    assert app.image_tag == "TestImageTag"
    assert app.image_tag_prefix == "TestBranch"
    assert len(app.events) == 1
    assert app.events[0].ready is True
    assert app.events[0].status_reason == "TestReason"
    assert app.events[0].status_message == "TestMessage"
    assert app.urls == ["https://TestHost/TestPath"]


def test_kollie_limits_urls_to_10(mocker, kustomization):

    ingress = mocker.MagicMock(spec=V1Ingress)
    ingress.spec = mocker.MagicMock(
        rules=[
            mocker.MagicMock(
                host="TestHost",
                http=mocker.MagicMock(
                    paths=[mocker.MagicMock(path=f"/TestPath{i}") for i in range(20)],
                ),
            )
        ]
    )

    app = KollieApp.from_resources(kustomization, ingress)

    assert len(app.urls) == 10


def test_kollie_environment_from_kustomizations(kustomization):
    kustomizations = [kustomization]
    env = KollieEnvironment.from_kustomizations(
        env_name="TestEnv",
        kustomizations=kustomizations,
        owner_email="test@owner.com",
        flux_repository_branch="test-branch",
    )
    assert env.name == "TestEnv"
    assert env.owner_email == "test@owner.com"
    assert env.flux_repository_branch == "test-branch"

    assert len(env.apps) == 1
    assert isinstance(env.apps[0], KollieApp)
    assert env.apps[0].name == "TestApp"
    assert env.apps[0].image_tag == "TestImageTag"
    assert env.apps[0].image_tag_prefix == "TestBranch"

    assert len(env.apps[0].events) == 1
    assert isinstance(env.apps[0].events[0], KollieAppEvent)
    assert env.apps[0].events[0].ready is True
    assert env.apps[0].events[0].status_reason == "TestReason"
    assert env.apps[0].events[0].status_message == "TestMessage"


def test_kollie_app_status_returns_placeholder_when_there_are_no_events():
    app = KollieApp(name="TestApp", env_name="TestEnv", owner_email="test@owner.com")

    assert app.status.ready is False
    assert app.status.type == "Unknown"
    assert app.status.status_reason == "No events"
    assert app.status.status_message == "No events have been recorded for this app."


def test_kollie_app_status_returns_last_event():
    app = KollieApp(name="TestApp", env_name="TestEnv", owner_email="test@owner.com")

    common_params = {"ready": False, "type": "Test", "status_reason": "Test"}

    e1 = KollieAppEvent(**common_params, status_message="Event1")
    e2 = KollieAppEvent(**common_params, status_message="Event2")
    e3 = KollieAppEvent(**common_params, status_message="Event3")

    app.events.extend([e1, e2, e3])

    assert app.status == e3
