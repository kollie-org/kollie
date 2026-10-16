import os
from unittest import mock

from fastapi.testclient import TestClient
from pytest import fixture

from kollie.app.main import create_app


@fixture
def test_client():
    with mock.patch("kollie.app.main.connect_to_cluster"):
        app = create_app()
        client = TestClient(app)
        yield client


@fixture(autouse=True)
def remove_x_auth_request_email_env_var():
    filtered = {k: v for k, v in os.environ.items() if k != "X_AUTH_REQUEST_EMAIL"}

    with mock.patch.dict(os.environ, filtered, clear=True):
        yield
