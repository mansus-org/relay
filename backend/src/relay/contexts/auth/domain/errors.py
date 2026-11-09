"""The ways auth says no. The api layer turns each one into a status code."""

from relay.shared.domain import DomainError


class AuthError(DomainError):
    """Base for everything the auth context refuses."""


class InvalidCredentialsError(AuthError):
    """Username and password do not add up to an account. Never say which half was wrong."""


class InvalidUsernameError(AuthError):
    """Not a username Relay will accept."""


class InvalidDisplayNameError(AuthError):
    """Nobody wants to be shown as a blank, or as a paragraph."""


class InvalidPasswordError(AuthError):
    """A password Relay will not accept, usually for length."""


class UsernameTakenError(AuthError):
    """Someone already registered that username."""


class InviteNotUsableError(AuthError):
    """An invite token cannot be registered with: unknown, already spent, or revoked."""


class InviteSpentError(InviteNotUsableError):
    """The invite is real but closed: someone registered with it, or it was pulled back.

    Kept apart from an unknown token because the person holding the link deserves to know
    the difference, and because the api answers them with different status codes.
    """


class InvalidTokenError(AuthError):
    """A token Relay will not accept: wrong signature, wrong kind, expired, or spent."""
