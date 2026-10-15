import datetime
from unittest.mock import patch

from kollie.models import EnvironmentMetadata, KollieEnvironment


@patch("kollie.app.ui.views.envs", autospec=True)
def test_create_env(mock_envs, test_client):
    response = test_client.post(
        "/create",
        data={"env_name": "test_env", "flux_repo_branch": "test_flux_branch"},
        headers={"X-AUTH-REQUEST-EMAIL": "test@owner.com"},
    )

    mock_envs.create_env.assert_called_once_with(
        env_name="test_env",
        flux_repo_branch="test_flux_branch",
        owner_email="test@owner.com"
    )
    assert response.status_code == 200
    assert response.template.name == "/envs/details.jinja2"


@patch("kollie.app.ui.views.applications")
def test_app_detail(mock_apps, test_client):
    response = test_client.get("/env/test_env/test_app")

    mock_apps.get_app.assert_called_once_with(env_name="test_env", app_name="test_app")
    assert response.status_code == 200
    assert response.template.name == "/apps/detail.jinja2"


@patch("kollie.app.ui.views.applications")
def test_app_edit(mock_apps, test_client):
    response = test_client.get("/env/test_env/test_app/edit")

    mock_apps.get_app.assert_called_once_with(env_name="test_env", app_name="test_app")
    assert response.status_code == 200
    assert response.template.name == "/apps/edit.jinja2"


@patch("kollie.app.ui.views.applications")
def test_app_save(mock_apps, test_client):
    response = test_client.post(
        "/env/test_env/test_app/save",
        data={"image_tag_prefix": "main"},
        follow_redirects=False,
    )

    mock_apps.update_app.assert_called_once_with(
        env_name="test_env",
        app_name="test_app",
        attributes=dict(image_tag_prefix="main"),
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/env/test_env/test_app"


@patch("kollie.app.ui.views.envs")
def test_select_bundle_obtains_bundles_from_service(mock_envs, test_client):
    # arrange
    mock_envs.get_env.return_value = KollieEnvironment(
        name="test_env",
        owner_email="test@owner.com",
        apps=[],
        flux_repository_branch=None
    )

    # act
    response = test_client.get("/env/foo/add-bundle")

    # assert
    mock_envs.get_available_app_bundles.assert_called_once()
    assert response.status_code == 200
    assert response.template.name == "/apps/add_bundle.jinja2"

    assert response.context["environment"].name == "test_env"
    assert response.context["environment"].owner_email == "test@owner.com"


@patch("kollie.app.ui.views.envs")
def test_select_bundle_raises_404_when_env_does_not_exist(mock_envs, test_client):
    # arrange
    mock_envs.get_env.return_value = None

    # act

    response = test_client.get("/env/foo/add-bundle")

    # assert
    assert response.status_code == 404


@patch("kollie.app.ui.views.envs")
def test_deploy_bundle_calls_service_method_correctly(mock_envs, test_client):
    # arrange
    mock_envs.get_env.return_value = KollieEnvironment(
        name="test_env",
        owner_email="test@owner.com",
        apps=[],
        flux_repository_branch=None
    )

    # act
    response = test_client.post(
        "/env/foo/add-bundle",
        data={"bundle_name": "test_bundle"},
        headers={"X-AUTH-REQUEST-EMAIL": "test@owner.com"},
    )

    # assert
    assert response.status_code == 200
    mock_envs.install_bundle.assert_called_once_with(
        env_name="foo", bundle_name="test_bundle", owner_email="test@owner.com"
    )


@patch("kollie.app.ui.views.envs")
def test_deploy_bundle_404(mock_envs, test_client):
    # arrange
    mock_envs.get_env.return_value = None

    # act
    response = test_client.post(
        "/env/foo/add-bundle",
        data={"bundle_name": "test_bundle"},
        headers={"X-AUTH-REQUEST-EMAIL": "test@owner.com"},
    )

    # assert
    assert response.status_code == 404
    mock_envs.deploy_app_bundle.assert_not_called()


def build_environment_metadata(name: str, owner_email: str) -> EnvironmentMetadata:
    return EnvironmentMetadata(
        name=name,
        owner_email=owner_email,
        created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        lease_exclusion_window=None,
    )


@patch("kollie.app.ui.views.envs", autospec=True)
def test_lists_the_users_own_environments_in_their_own_section_when_authenticated(
    mock_envs, test_client
):
    """
    GIVEN running environments with several owners
    WHEN the environment index is requested
    AND the request is authenticated as one of those owners
    THEN that owner's environments are listed in their own section
    AND every environment is still listed in the full list
    """
    # Given
    my_environment = build_environment_metadata("env-mine", "me@owner.com")
    other_environment_a = build_environment_metadata("env-a", "someone@owner.com")
    other_environment_b = build_environment_metadata("env-b", "another@owner.com")
    mock_envs.list_envs.return_value = [
        other_environment_a,
        other_environment_b,
        my_environment,
    ]

    # When
    response = test_client.get("/", headers={"X-AUTH-REQUEST-EMAIL": "me@owner.com"})

    # Then
    assert response.status_code == 200
    assert response.context["my_environments"] == [my_environment]
    assert response.context["all_environments"] == [
        other_environment_a,
        other_environment_b,
        my_environment,
    ]
    assert "My environments" in response.text
    assert "All environments" in response.text


@patch("kollie.app.ui.views.envs", autospec=True)
def test_asks_the_user_to_sign_in_when_the_user_is_unknown(mock_envs, test_client):
    """
    GIVEN running environments with several owners
    WHEN the environment index is requested
    AND the request carries no user information
    THEN every environment is listed in the full list
    AND the personal section asks the user to sign in
    """
    # Given
    environment_a = build_environment_metadata("env-a", "someone@owner.com")
    environment_b = build_environment_metadata("env-b", "another@owner.com")
    mock_envs.list_envs.return_value = [environment_a, environment_b]

    # When
    response = test_client.get("/")

    # Then
    assert response.status_code == 200
    assert response.context["my_environments"] is None
    assert response.context["all_environments"] == [environment_a, environment_b]
    assert "Sign in to see your environments" in response.text


@patch("kollie.app.ui.views.envs", autospec=True)
def test_shows_an_empty_own_section_when_the_user_owns_nothing(mock_envs, test_client):
    """
    GIVEN running environments owned by other people
    WHEN the environment index is requested
    AND the request is authenticated as a user who owns none of them
    THEN the user's section is shown with an empty state
    """
    # Given
    environment_a = build_environment_metadata("env-a", "someone@owner.com")
    mock_envs.list_envs.return_value = [environment_a]

    # When
    response = test_client.get("/", headers={"X-AUTH-REQUEST-EMAIL": "me@owner.com"})

    # Then
    assert response.status_code == 200
    assert response.context["my_environments"] == []
    assert response.context["all_environments"] == [environment_a]
    assert "You have no running environments" in response.text
