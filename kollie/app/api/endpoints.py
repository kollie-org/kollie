from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from kollie.app.auth import UserInfo, authenticated_user
from kollie.models import EnvironmentMetadata, KollieEnvironment
from kollie.persistence import AppTemplate, get_app_template_store
from kollie.service import envs

router = APIRouter(prefix="/api")


@router.get("/")
async def main():
    return {"message": "Hello!!!"}


@router.get("/apps", response_model=None)
async def apps() -> list[AppTemplate]:
    templates = get_app_template_store()
    return templates.get_all()


@router.get("/env")
async def environment_index() -> list[EnvironmentMetadata]:
    return envs.list_envs()


@router.get("/env/{environment_name}")
async def environment_details(environment_name: str) -> KollieEnvironment:
    environment = envs.get_env(environment_name)

    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    return environment


@router.post("/env", status_code=201)
async def create_environment(
    user: Annotated[UserInfo, Depends(authenticated_user)],
    env_name: Annotated[str, Body()],
    flux_repo_branch: Annotated[str | None, Body()] = None,
) -> KollieEnvironment | None:
    envs.create_env(
        env_name=env_name,
        owner_email=user.email,
        flux_repo_branch=flux_repo_branch
    )

    return envs.get_env(env_name)


@router.delete("/env/{environment_name}", status_code=204)
async def delete_environment(
    environment_name: str, user: Annotated[UserInfo, Depends(authenticated_user)]
):
    envs.delete_env(environment_name)


@router.get("/debug")
async def debug(request: Request):
    return {"headers": dict(request.headers)}


@router.get("/userinfo")
async def userinfo(
    user: Annotated[UserInfo, Depends(authenticated_user)]
) -> UserInfo | None:
    return user
