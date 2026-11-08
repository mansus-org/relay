"""bcrypt: slow on purpose, so a stolen database is not a list of passwords."""

import bcrypt

from relay.contexts.auth.domain.ports import PasswordHasher

# bcrypt's default, and the point where hashing an honest password is still instant
# and brute-forcing a stolen dump is still expensive. The domain turns away anything
# past 72 bytes before it gets here, because bcrypt would silently ignore the rest.
_COST = 12

# A hash of a string nobody will ever type, kept only so that a login against an account
# that does not exist still costs a full bcrypt. Without it, "no such user" answers in a
# microsecond and "wrong password" in a tenth of a second, which is a list of accounts
# for anyone who cares to time it. Its own cost has to be _COST, or the cheap answer is
# back; a test in tests/unit/test_passwords.py is what keeps the two in step.
_NO_SUCH_ACCOUNT = b"$2b$12$rOwiX37Qrun29tQqoJXhZ.bRBECqmJ9mEU3WyMIwuaqzn/1.eptDa"


class BcryptPasswordHasher(PasswordHasher):
    """Hashes passwords with bcrypt, salt included in the string that comes back."""

    def hash(self, raw: str) -> str:
        return bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=_COST)).decode()

    def verify(self, raw: str, hashed: str | None) -> bool:
        try:
            if hashed is None:
                bcrypt.checkpw(raw.encode(), _NO_SUCH_ACCOUNT)
                return False
            return bcrypt.checkpw(raw.encode(), hashed.encode())
        except ValueError:
            # bcrypt refuses a password longer than it can read, and a stored hash this code
            # never wrote is not a match either. Neither is allowed to be anything but "no".
            return False
