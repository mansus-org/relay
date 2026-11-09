"""The access token: a signed claim about who is calling, checked without asking the database."""

from datetime import timedelta

from jose import ExpiredSignatureError, JWTError, jwt

from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.ports import TokenBroker
from relay.shared.application import Clock

_ALGORITHM = "HS256"


class JwtTokenBroker(TokenBroker):
    """Signs access tokens with the app's secret and trusts nothing else.

    Refresh tokens are not here on purpose: they are random strings kept in a table,
    because the one thing a signed token cannot do is be taken back.
    """

    def __init__(self, secret: str, clock: Clock, *, issuer: str = "relay") -> None:
        if not secret:
            raise ValueError("Nothing to sign with: set SECRET_KEY.")
        self._secret = secret
        self._clock = clock
        self._issuer = issuer

    def access_token_for(self, user_id: int, *, lifetime: timedelta) -> str:
        now = self._clock.now()
        claims = {"sub": str(user_id), "iat": now, "exp": now + lifetime, "iss": self._issuer}
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def user_id_of(self, token: str) -> int:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[_ALGORITHM], issuer=self._issuer)
            return int(claims["sub"])
        except ExpiredSignatureError as error:
            raise InvalidTokenError("That access token has run out; go get another.") from error
        except (JWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError("That access token is not one of ours.") from error
