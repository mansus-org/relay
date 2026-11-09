"""What an admin can see of an account, and what they are allowed to do to it."""

from datetime import datetime

from relay.contexts.admin.domain.errors import MemberCannotBeDeactivatedError
from relay.contexts.auth.domain.user import User
from relay.shared.domain import ValueObject


class MemberSummary(ValueObject):
    """One account as the member list shows it.

    Flat, and with no password hash in it: this is built by one statement over the users
    table and it has no business dragging a hash along for a hundred accounts to show
    somebody a username.

    There are no post counts here, which is not an oversight. Posts attribute their author
    with the placeholder UUID identity RELY-04 shipped with, and accounts are integer ids;
    there is no join between the two until that placeholder is replaced, and a count built
    on a guessed join would be worse than no count.
    """

    id: int
    username: str
    display_name: str
    is_admin: bool
    created_at: datetime
    deactivated_at: datetime | None = None

    @property
    def is_deactivated(self) -> bool:
        return self.deactivated_at is not None


def can_deactivate(*, admin: User, target: MemberSummary) -> None:
    """Whether this admin may switch this account off.

    Two answers are no, and both live here rather than in the endpoint so a second caller
    cannot fail to notice them.

    Yourself: an admin who can switch themselves off holds a way to lock themselves out
    of the only tool that could switch them back on, and a Relay whose last admin does
    that is a Relay nobody runs.

    Another admin: deactivating is one admin acting on the membership, not one admin
    overruling another. Whoever has to be out of a Relay is taken out as an admin first,
    at the prompt, where it is on the record who did it.
    """
    if target.is_admin:
        raise MemberCannotBeDeactivatedError(
            "An admin cannot be deactivated. Make them a member first."
        )
    if target.id == admin.require_id():
        raise MemberCannotBeDeactivatedError("You cannot deactivate your own account.")
