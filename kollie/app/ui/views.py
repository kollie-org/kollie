import pathlib
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from kollie.app.auth import UserInfo, authenticated_user, userinfo
from kollie.app.ui.templatefilters import humanise_date_filter
from kollie.app.ui.viewmodels import render_resources
from kollie.exceptions import KollieException
from kollie.models import EnvironmentMetadata
from kollie.persistence import get_app_template_store
from kollie.service import applications, envs

router = APIRouter(default_response_class=HTMLResponse)


def add_relative_url_for_into_jinja_context(request: Request):
    """
    This is a damn hack for getting jinja to generate relative urls
    so that the http/https scheme works correctly.

    Starlette/FastAPI for some reason insists on generating absolute urls
    but does a bad job figuring out the scheme and blames it on nginx and
    uvicorn rather than just generating relative urls.

    See: https://github.com/encode/starlette/issues/538

    This function exposes `relative_url_for` into the jinja context
    so that function can be used in the templates.

    We are still using the same function that `url_for` calls under the hood
    """
    return {"relative_url_for": router.url_path_for}


def add_userinfo_into_jinja_context(
    request: Request,
):
    return {"userinfo": userinfo(request)}


def _init_templates() -> Jinja2Templates:
    """
    Factory function for setting up Jinja2 Templates configuration
    TODO: Move this to a better location
    """
    tpl = Jinja2Templates(
        directory=f"{pathlib.Path(__file__).parent.resolve()}/templates",
        context_processors=[
            add_relative_url_for_into_jinja_context,
            add_userinfo_into_jinja_context,
        ],
    )
    tpl.env.add_extension("jinja2.ext.debug")
    tpl.env.filters["humanise"] = humanise_date_filter

    return tpl


templates = _init_templates()


def _select_environments_owned_by(
    *, environments: list[EnvironmentMetadata], owner_email: str
) -> list[EnvironmentMetadata]:
    """
    Keeps environments owned by owner_email, preserving the incoming order.
    """
    owned_environments: list[EnvironmentMetadata] = []

    for environment in environments:
        if environment.owner_email == owner_email:
            owned_environments.append(environment)

    return owned_environments


@router.get("/")
async def environment_index(
    request: Request, owner: str | None = None, q: str | None = None
):
    running_environments = envs.list_envs(owner_email=owner)
    current_user = userinfo(request)
    search_term = q or ""

    my_environments: list[EnvironmentMetadata] | None = None
    if current_user is not None:
        my_environments = _select_environments_owned_by(
            environments=running_environments, owner_email=current_user.email
        )

    # Filtering by search_term happens in the browser (static/environment_search.js)
    # so the full list is always rendered; the term is only echoed into the
    # search input so that shared links and reloads restore the same view.
    return templates.TemplateResponse(
        request,
        "/index.jinja2",
        {
            "my_environments": my_environments,
            "all_environments": running_environments,
            "search_term": search_term,
        },
    )


@router.get("/create")
async def create_environment(
    request: Request,
    user: Annotated[UserInfo, Depends(authenticated_user)],
):
    app_templates = get_app_template_store()

    return templates.TemplateResponse(
        request,
        "/create.jinja2",
        {"available_apps": app_templates.get_all()},
    )


@router.post("/delete/{testenv_name}")
async def delete_environment(
    request: Request,
    testenv_name: str,
    user: Annotated[UserInfo, Depends(authenticated_user)],
):
    envs.delete_env(testenv_name)
    return RedirectResponse(
        url=router.url_path_for("environment_index"), status_code=302
    )


@router.post("/create")
async def handle_create_env(
    request: Request,
    user: Annotated[UserInfo, Depends(authenticated_user)],
    env_name: Annotated[str, Form()],
    flux_repo_branch: Annotated[str | None, Form()] = None
):
    envs.create_env(
        env_name=env_name,
        owner_email=user.email,
        flux_repo_branch=flux_repo_branch
    )

    return RedirectResponse(
        url=router.url_path_for("env_detail", testenv_name=env_name),
        status_code=302,
    )


@router.get("/env/{testenv_name}")
async def env_detail(request: Request, testenv_name: str):
    environment = envs.get_env(testenv_name)
    ctx = {
        "environment": environment,
        "allow_extended_lease": any(candidate in testenv_name for candidate in envs.EXTENDED_LEASE_TEST_ENV_NAMES) if envs.EXTENDED_LEASE_TEST_ENV_NAMES else False,
    }
    return templates.TemplateResponse(
        request, "/envs/details.jinja2", ctx
    )


@router.post("/env/{env_name}/extend-lease")
async def extend_lease(
    request: Request,
    env_name: str,
    hour: Annotated[int, Form()],
    user: Annotated[UserInfo, Depends(authenticated_user)],
    days: Annotated[int, Form()] = 0,
):
    envs.extend_lease(env_name, hour, days)

    return RedirectResponse(
        url=router.url_path_for("env_detail", testenv_name=env_name),
        status_code=302,
    )


@router.get("/env/{env_name}/add-app")
async def add_app_to_env(
    request: Request,
    env_name: str,
):
    environment = envs.get_env(env_name)

    if environment:
        available_apps = envs.get_available_apps(environment)

    return templates.TemplateResponse(
        request,
        "/apps/add.jinja2",
        {
            "environment": environment,
            "available_apps": available_apps,
        },
    )


@router.get("/env/{env_name}/add-bundle")
async def select_bundle(
    request: Request,
    env_name: str,
):
    environment = envs.get_env(env_name)

    if not environment:
        raise HTTPException(
            status_code=404, detail=f"Environment `{env_name}` not found"
        )

    available_bundles = envs.get_available_app_bundles(env_name)

    installed_apps = [app.name for app in environment.apps]

    installed_bundles = [
        bundle.name
        for bundle in available_bundles
        if all(app in installed_apps for app in bundle.apps)
    ]

    return templates.TemplateResponse(
        request,
        "/apps/add_bundle.jinja2",
        {
            "environment": environment,
            "available_bundles": available_bundles,
            "installed_apps": installed_apps,
            "installed_bundles": installed_bundles,
        },
    )


@router.post("/env/{env_name}/add-bundle")
async def deploy_bundle(
    request: Request,
    env_name: str,
    bundle_name: Annotated[str, Form()],
    user: Annotated[UserInfo, Depends(authenticated_user)],
):
    environment = envs.get_env(env_name)
    if not environment:
        raise HTTPException(
            status_code=404, detail=f"Environment `{env_name}` not found"
        )

    envs.install_bundle(
        env_name=env_name, bundle_name=bundle_name, owner_email=user.email
    )

    return RedirectResponse(
        url=router.url_path_for("env_detail", testenv_name=env_name),
        status_code=302,
    )


@router.post("/env/{env_name}/add-app")
async def save_app_to_env(
    env_name: str,
    app_name: Annotated[str, Form()],
    user: Annotated[UserInfo, Depends(authenticated_user)],
    image_tag_prefix: Annotated[str | None, Form()] = None,
):
    applications.create_app(
        app_name=app_name,
        env_name=env_name,
        owner_email=user.email,
        image_tag_prefix=image_tag_prefix,
    )

    return RedirectResponse(
        url=router.url_path_for("env_detail", testenv_name=env_name),
        status_code=302,
    )


@router.post("/env/{env_name}/{app_name}/delete")
async def delete_app_from_env(
    request: Request,
    env_name: str,
    app_name: str,
):
    applications.delete_app(env_name=env_name, app_name=app_name)

    return RedirectResponse(
        url=router.url_path_for("env_detail", testenv_name=env_name),
        status_code=302,
    )


async def _get_app_and_render(
    request: Request, env_name: str, app_name: str, template: str
):
    """
    Fetches the app and renders the specified template.
    """
    try:
        app = applications.get_app(env_name=env_name, app_name=app_name)
        resources = render_resources(app, templates)

        return templates.TemplateResponse(
            request,
            template,
            {
                "env_name": env_name,
                "app": app,
                "resources": resources,
            },
        )
    except KollieException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/env/{env_name}/{app_name}")
async def app_detail(request: Request, env_name: str, app_name: str):
    """
    Returns the details of a specific app in an environment and renders it.
    """
    return await _get_app_and_render(request, env_name, app_name, "/apps/detail.jinja2")


@router.get("/env/{env_name}/{app_name}/edit")
async def app_edit(request: Request, env_name: str, app_name: str):
    """
    Edit configuration of an app in a specified environment.
    """
    return await _get_app_and_render(request, env_name, app_name, "/apps/edit.jinja2")


@router.post("/env/{env_name}/{app_name}/save")
async def app_save(
    request: Request, env_name: str, app_name: str, image_tag_prefix: Annotated[str, Form()]
):
    """
    Edit configuration of an app in a specified environment.
    """
    applications.update_app(
        env_name=env_name,
        app_name=app_name,
        attributes={"image_tag_prefix": image_tag_prefix},
    )

    return RedirectResponse(
        url=router.url_path_for("app_detail", env_name=env_name, app_name=app_name),
        status_code=302,
    )
