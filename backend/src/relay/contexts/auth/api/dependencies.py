"""Asking a request who is calling, from the bearer token it sent."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from relay.container import Container
from relay.contexts.auth.application import ReadAuthenticatedUser
from relay.contexts.auth.domain.errors import AccountDeactivatedError, InvalidTokenError
from relay.contexts.auth.domain.user import User
from relay.shared.api.dependencies import get_container

# auto_error=False so a missing or oddly spelled header comes back as None and we
# answer 401 like every other way in, instead of FastAPI's 403.
_bearer = HTTPBearer(auto_error=False)


def get_read_authenticated_user(
    container: Annotated[Container, Depends(get_container)],
) -> ReadAuthenticatedUser:
    return container.get_read_authenticated_user()


async def get_current_user(
    read_user: Annotated[ReadAuthenticatedUser, Depends(get_read_authenticated_user)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """The account a bearer access token belongs to.

    Any route can ask for it: `user: CurrentUser`. Other contexts may import this
    one function from auth; it is the one thing auth is for.
    """
    if credentials is None:
        raise _unauthorized("Send an access token as a bearer token.")
    try:
        return await read_user.execute(credentials.credentials)
    except AccountDeactivatedError as error:
        raise _forbidden(str(error)) from error
    except InvalidTokenError as error:
        raise _unauthorized(str(error)) from error


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    """Only the people who run this Relay. Any route can ask for it: `admin: AdminUser`.

    It is `get_current_user` with one more question, so a stranger and a signed-in
    neighbour are refused in two different ways: 401 says "I do not know you", 403 says
    "I know you, and this is not yours to do". Being an admin is a column an operator
    sets, never something this API hands out - there is no route anywhere that writes it.
    """
    if not user.is_admin:
        raise _forbidden("That is for the people who run Relay.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
