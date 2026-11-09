"""The ways moderation says no. The api layer turns each one into a status code."""

from relay.shared.domain import ConflictError, NotFoundError


class MemberNotFoundError(NotFoundError):
    """No account answers to that number."""


class InviteNotFoundError(NotFoundError):
    """No invite answers to that number."""


class AlreadyInThatStateError(ConflictError):
    """What the request asked for is already the case, so there is nothing to do.

    One class covers a post that is already approved, an account that is already off,
    an invite already spent: from outside it is always the same answer, no, and here
    is what it currently is. Doing it again would also write a second line to the log
    for a decision that was not made twice.
    """


class MemberCannotBeDeactivatedError(ConflictError):
    """An account this API is not allowed to switch off.

    Your own, because an admin who locks themselves out has nobody left to unlock them,
    and another admin's, because two people who can each switch the other off have not
    settled who is in charge.
    """
