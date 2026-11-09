"""HTTP edge of the auth context: get in, get back in, and find out who you are."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from relay.container import Container
from relay.contexts.auth.api.dependencies import CurrentUser
from relay.contexts.auth.application import (
    Login,
    RefreshAccessToken,
    RegisterWithInvite,
    UpdateDisplayName,
)
from relay.contexts.auth.domain.errors import (
    InvalidCredentialsError,
    InvalidDisplayNameError,
    InvalidPasswordError,
    InvalidTokenError,
    InvalidUsernameError,
    InviteNotUsableError,
    InviteSpentError,
    UsernameTakenError,
)
from relay.contexts.auth.domain.tokens import ACCESS_LIFETIME, TokenPair
from relay.contexts.auth.domain.user import User
from relay.shared.api.dependencies import get_container

router = APIRouter(prefix="/auth", tags=["auth"])

# Long enough for any real token or name, short enough that a request cannot bury the
# password hasher in megabytes before the domain gets to say what it thinks.
_MAX_TOKEN_CHARS = 512
_MAX_USERNAME_CHARS = 40
_MAX_PASSWORD_CHARS = 200
_MAX_DISPLAY_NAME_CHARS = 120


class RegisterRequest(BaseModel):
    """A new account, paid for with an invite."""

    invite_token: str = Field(
        min_length=1, max_length=_MAX_TOKEN_CHARS, description="The token from the invite link."
    )
    username: str = Field(
        min_length=1, max_length=_MAX_USERNAME_CHARS, description="Lowercase, 3-20 of a-z 0-9 . _ -"
    )
    password: str = Field(
        min_length=1, max_length=_MAX_PASSWORD_CHARS, description="At least 8 characters."
    )
    display_name: str = Field(
        min_length=1,
        max_length=_MAX_DISPLAY_NAME_CHARS,
        description="What to call you, up to 60 characters.",
    )

    @field_validator("invite_token", "username", "display_name")
    @classmethod
    def _no_stray_space(cls, value: str) -> str:
        """Nobody ever meant a space at either end of one of these; empty is the domain's call."""
        return value.strip()


class LoginRequest(BaseModel):
    """An account and the password for it. Both are checked together, or not at all."""

    username: str = Field(min_length=1, max_length=_MAX_USERNAME_CHARS)
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_CHARS)


class RefreshRequest(BaseModel):
    """The refresh token from the last time round."""

    refresh_token: str = Field(min_length=1, max_length=_MAX_TOKEN_CHARS)


class ProfileUpdateRequest(BaseModel):
    """What you are allowed to change about your own account. One field, for now.

    The length cap here is looser than the one in the domain on purpose, so that a name
    too long to keep is refused with the sentence that says why, not with a schema error.
    """

    display_name: str = Field(
        min_length=1,
        max_length=_MAX_DISPLAY_NAME_CHARS,
        description="What to call you, up to 60 characters.",
    )

    @field_validator("display_name")
    @classmethod
    def _no_stray_space(cls, value: str) -> str:
        """Nobody ever meant a space at either end of a name; empty is the domain's call."""
        return value.strip()


class TokenResponse(BaseModel):
    """Both halves of a session. Send the access token with every call; keep the other."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - an OAuth field, not a secret
    expires_in_seconds: int

    @classmethod
    def from_domain(cls, tokens: TokenPair) -> "TokenResponse":
        return cls(
            access_token=tokens.access_token,
            refresh_token=str(tokens.refresh_token),
            expires_in_seconds=int(ACCESS_LIFETIME.total_seconds()),
        )


class UserResponse(BaseModel):
    """Who the access token belongs to."""

    id: int
    username: str
    display_name: str
    is_admin: bool

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.require_id(),
            username=str(user.username),
            display_name=str(user.display_name),
            is_admin=user.is_admin,
        )


def get_register_with_invite(
    container: Annotated[Container, Depends(get_container)],
) -> RegisterWithInvite:
    return container.get_register_with_invite()


def get_login(container: Annotated[Container, Depends(get_container)]) -> Login:
    return container.get_login()


def get_refresh_access_token(
    container: Annotated[Container, Depends(get_container)],
) -> RefreshAccessToken:
    return container.get_refresh_access_token()


def get_update_display_name(
    container: Annotated[Container, Depends(get_container)],
) -> UpdateDisplayName:
    return container.get_update_display_name()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open an account with an invite",
    description=(
        "Relay is invite-only: without a live invite there is no way in. The invite is "
        "spent here, so it cannot be used twice, and you get a session straight away."
    ),
    responses={
        400: {"description": "The username, password or display name breaks a rule"},
        403: {"description": "That invite exists and is shut: already used, or pulled back"},
        404: {"description": "No invite matches that token"},
        409: {"description": "Someone already has that username"},
    },
)
async def register(
    body: RegisterRequest,
    use_case: Annotated[RegisterWithInvite, Depends(get_register_with_invite)],
) -> TokenResponse:
    try:
        registration = await use_case.execute(
            invite_token=body.invite_token,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
        )
    except InviteSpentError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except InviteNotUsableError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UsernameTakenError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (InvalidUsernameError, InvalidPasswordError, InvalidDisplayNameError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return TokenResponse.from_domain(registration.tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange a username and password for a session",
    description=(
        "Wrong username and wrong password get the same answer, so this cannot be used "
        "to find out which accounts exist."
    ),
    responses={401: {"description": "No such account, or the password does not match"}},
)
async def login(
    body: LoginRequest,
    use_case: Annotated[Login, Depends(get_login)],
) -> TokenResponse:
    try:
        tokens = await use_case.execute(username=body.username, password=body.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return TokenResponse.from_domain(tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Trade in a refresh token for a new pair",
    description=(
        "The old refresh token stops working here: each one is good once, so a token "
        "that has been spent cannot buy anything again."
    ),
    responses={401: {"description": "Never issued, already used, revoked, or out of date"}},
)
async def refresh(
    body: RefreshRequest,
    use_case: Annotated[RefreshAccessToken, Depends(get_refresh_access_token)],
) -> TokenResponse:
    try:
        tokens = await use_case.execute(body.refresh_token)
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return TokenResponse.from_domain(tokens)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Who the access token belongs to",
    description="The one place a client can check that its token still works.",
    responses={401: {"description": "No bearer token, or not one we signed"}},
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_domain(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Change what Relay calls you",
    description=(
        "Only the display name is yours to change. The handle you log in with stays put, "
        "because everything already written about you leans on it."
    ),
    responses={
        400: {"description": "The display name breaks a rule"},
        401: {"description": "No bearer token, or not one we signed"},
        404: {"description": "The account behind that token is gone"},
    },
)
async def update_profile(
    body: ProfileUpdateRequest,
    user: CurrentUser,
    use_case: Annotated[UpdateDisplayName, Depends(get_update_display_name)],
) -> UserResponse:
    try:
        updated = await use_case.execute(user_id=user.require_id(), display_name=body.display_name)
    except InvalidDisplayNameError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return UserResponse.from_domain(updated)
