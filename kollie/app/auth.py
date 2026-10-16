"""
This submodule contains application level authentication logic.

Authentication for Kollie is primarily handled out of bands at the proxy level
by OAuth2Proxy via nginx-ingress' auth_request configuration. Kollie expects
user information to be made available as request headers for authenticated
requests. When Kollie runs behind nginx + OAuth2Proxy, it expects the following
headers to be present:
    - x-auth-request-user (The federated user_id from Google - not important)
    - x-auth-request-email (The email address of the authenticated user)
    - x-auth-request-groups (Google groups that the user is part of. Comma separated)

Local development:
This submodule contains some developer eargonomics to take the
x-auth-request-email from environment variables to help with local development

NOTE: OAuth2 proxy will be configured differently for API routes compared to
UI routes. For API routes, a token valid token is required in the Authorization
header. UI routes are authenticated by first going through the OAuth login flow
and then maintaining a sticky session. This means standalone UIs should have
OAuth2 proxy put in front of it to obtain a token which is then included in the
header when making calls to the API.
"""

import logging
import os
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    email: str
    user_id: str | None = None


def authenticated_user(request: Request) -> UserInfo:
    """
    Returns the authenticated user (via userinfo) or raises an HTTPException
    """
    if user := userinfo(request):
        return user

    raise HTTPException(
        status_code=status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED,
        detail="Endpoint requires proxy-level authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


def userinfo(request: Request) -> UserInfo | None:
    """
    Attempts to load userinformation from request headers (or env vars)
    Returns None if neither is successful.
    """
    x_auth_request_email = request.headers.get("x-auth-request-email")
    x_auth_request_user = request.headers.get("x-auth-request-user")

    # We simulate the `X-AUTH-REQUEST-EMAIL` header in local environments
    # for ease of development
    if dev_user := os.environ.get("X_AUTH_REQUEST_EMAIL"):
        x_auth_request_email = dev_user

        logger.warning(
            """
            Using X-AUTH-REQUEST-EMAIL from environment variable.
            This should only be used for local development
            """
        )

    if x_auth_request_email is None:
        return None

    return UserInfo(email=x_auth_request_email, user_id=x_auth_request_user)
