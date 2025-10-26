from unittest import mock
from unittest.mock import patch
import pytest
from kollie.cluster.image_update_automation import (
    handle_image_policy_event,
    watch_for_image_updates,
)


@pytest.fixture(autouse=True)
def patch_connect_to_cluster():
    with patch("kollie.app.main.connect_to_cluster"):
        yield


@pytest.fixture()
def dummy_image_policy():
    yield {
        "apiVersion": "image.toolkit.fluxcd.io/v1",
        "kind": "ImagePolicy",
        "metadata": {
            "labels": {
                "tails-app-environment": "foobar",
                "tails-app-name": "boofar",
                "tails-app-stage": "testing",
            },
            "name": "foobar-boofar",
        },
        "spec": {},
        "status": {
            "conditions": [],
            "latestRef": {
                "name": "repository.local/boofar",
                "tag": "main-latest"
            },
            "observedGeneration": 1,
        },
    }


@patch("kollie.cluster.image_update_automation.find_image_policies")
@patch("kollie.cluster.image_update_automation.applications.update_app")
def test_handle_image_update_policy_event_queries_image_policy_for_latest_tag(
    update_app_mock, find_image_policies_mock, dummy_image_policy
):
    # arrange

    find_image_policies_mock.return_value = {"items": [dummy_image_policy]}

    # prepare an event for the image policy but having a different latestTag
    event = {"type": "UPDATE", "object": {**dummy_image_policy}}
    event["object"]["status"]["latestRef"]["tag"] = "main-not-latest"

    # act
    handle_image_policy_event(event)

    # assert
    find_image_policies_mock.assert_called_once_with(
        env_name="foobar", app_name="boofar"
    )
    update_app_mock.assert_called_once_with(
        env_name="foobar",
        app_name="boofar",
        attributes={"image_tag": "main-not-latest"},
    )


@patch("kollie.cluster.image_update_automation.find_image_policies")
@patch("kollie.cluster.image_update_automation.applications.update_app")
@patch("kollie.cluster.image_update_automation.logger")
def test_handle_image_update_policy_event_no_image_policy(
    logger_mock,
    update_app_mock,
    find_image_policies_mock,
    dummy_image_policy,
):
    # arrange
    event = {
        "type": "ADDED",
        "object": {**dummy_image_policy},
    }

    find_image_policies_mock.return_value = {"items": []}

    # act

    handle_image_policy_event(event)

    # assert
    update_app_mock.assert_not_called()
    logger_mock.warning.assert_called_once_with(
        "No image policy found for event",
        app_name="boofar",
        env_name="foobar",
        event_data=event,
    )


@patch("kollie.cluster.image_update_automation.find_image_policies")
@patch("kollie.cluster.image_update_automation.applications.update_app")
@patch("kollie.cluster.image_update_automation.logger")
def test_handle_image_update_policy_event_no_latest_image(
    logger_mock,
    update_app_mock,
    find_image_policies_mock,
    dummy_image_policy,
):
    # arrange

    # prepare an ImagePolicy that doesn't have a latestTag
    image_policy = {**dummy_image_policy}
    image_policy["status"] = {"conditions": [], "observedGeneration": 1}

    event = {
        "type": "ADDED",
        "object": {**image_policy},
    }

    find_image_policies_mock.return_value = {"items": [image_policy]}

    # act
    handle_image_policy_event(event)

    # assert
    update_app_mock.assert_not_called()
    logger_mock.warning.assert_called_once_with(
        "skip.latestRef_not_found", image_policy=image_policy
    )


@patch("kollie.cluster.image_update_automation.logger")
def test_handle_image_update_policy_event_with_missing_key(mock_logger):
    event = {
        "object": {
            "metadata": {
                "name": "test",
                "namespace": "test",
                "labels": {"tails-app-name": "test"},
            }
        }
    }
    handle_image_policy_event(event)
    mock_logger.warning.assert_called_once()


@patch("kollie.cluster.image_update_automation.logger")
@patch("kollie.cluster.image_update_automation.find_image_policies")
@patch("kollie.cluster.image_update_automation.applications.update_app")
def test_handle_image_update_policy_event_with_multiple_matching_image_policies(
    update_app_mock, mock_find_image_policies, mock_logger
):
    event = {
        "object": {
            "metadata": {
                "labels": {"tails-app-environment": "test", "tails-app-name": "test"}
            }
        }
    }
    mock_find_image_policies.return_value = {
        "items": [
            {"status": {"latestRef": {"name": "123", "tag": "456"}}},
            {"status": {"latestRef": {"name": "789", "tag": "012"}}},
        ]
    }
    handle_image_policy_event(event)
    update_app_mock.assert_called_once_with(
        env_name="test",
        app_name="test",
        attributes={"image_tag": "456"},
    )
    mock_logger.warning.assert_not_called()


@patch("kollie.cluster.image_update_automation.watch.Watch")
@patch("kollie.cluster.image_update_automation.client.CustomObjectsApi")
@patch("kollie.cluster.image_update_automation.handle_image_policy_event")
def test_watch_for_image_updates(mock_handle_event, mock_api, mock_watch):
    mock_event = {
        "object": {
            "metadata": {
                "labels": {"tails-app-environment": "test", "tails-app-name": "test"}
            }
        }
    }
    mock_watch.return_value.stream.return_value = [mock_event]

    watch_for_image_updates()

    mock_api.assert_called_once()
    mock_watch.assert_called_once()
    mock_handle_event.assert_called_once_with(mock_event)


@patch("kollie.cluster.image_update_automation.watch.Watch")
@patch("kollie.cluster.image_update_automation.client.CustomObjectsApi")
@patch("kollie.cluster.image_update_automation.handle_image_policy_event")
@patch("kollie.cluster.image_update_automation.logger")
def test_watch_for_image_updates_unhandled_exception(
    mock_logger, mock_handle_event, mock_api, mock_watch
):
    mock_event = {
        "object": {
            "metadata": {
                "labels": {"tails-app-environment": "test", "tails-app-name": "test"}
            }
        }
    }
    mock_watch.return_value.stream.return_value = [mock_event]
    mock_handle_event.side_effect = Exception("Something bad happened")

    watch_for_image_updates()

    mock_api.assert_called_once()
    mock_watch.assert_called_once()
    mock_handle_event.assert_called_once_with(mock_event)
    mock_logger.error.assert_called_once_with(
        "image_update_automation.failed", error=mock.ANY, image_policy_event=mock_event
    )


@patch("kollie.cluster.image_update_automation.watch.Watch")
@patch("kollie.cluster.image_update_automation.logger")
def test_keyboard_interrupt(mock_logger, mock_watch):
    mock_watch.return_value.stream.side_effect = KeyboardInterrupt
    watch_for_image_updates()
    mock_watch.return_value.stream.assert_called_once()
    mock_logger.info.assert_called_once_with("Graceful shutdown initiated")


@patch("kollie.cluster.image_update_automation.watch.Watch")
@patch("kollie.cluster.image_update_automation.logger")
def test_system_exit(mock_logger, mock_watch):
    mock_watch.return_value.stream.side_effect = SystemExit
    watch_for_image_updates()
    mock_watch.return_value.stream.assert_called_once()
    mock_logger.info.assert_called_once_with("Graceful shutdown initiated")
