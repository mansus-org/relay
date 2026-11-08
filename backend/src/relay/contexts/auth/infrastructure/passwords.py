"""bcrypt: slow on purpose, so a stolen database is not a list of passwords."""

import bcrypt

from relay.contexts.auth.domain.ports import PasswordHasher

# bcrypt's default, and the point where hashing an honest password is still instant
# and brute-forcing a stolen dump is still expensive. The domain turns away anything
# past 72 bytes before it gets here, because bcrypt would silently ignore the rest.
_COST = 12


class BcryptPasswordHasher(PasswordHasher):
    """Hashes passwords with bcrypt, salt included in the string that comes back."""

    def hash(self, raw: str) -> str:
        return bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=_COST)).decode()

    def verify(self, raw: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(raw.encode(), hashed.encode())
        except ValueError:
            # A stored hash this code never wrote is not a wrong password; it is a broken row.
            return False
