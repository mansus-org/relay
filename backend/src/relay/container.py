from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.auth import infrastructure as auth
from relay.contexts.auth.application import (
    EnsureFirstAdmin,
    IssueTokens,
    Login,
    ReadAuthenticatedUser,
    RefreshAccessToken,
    RegisterWithInvite,
)
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.ports import PasswordHasher, TokenBroker
from relay.contexts.location.application import ResolvePostalCode
from relay.contexts.location.infrastructure import DatasetPostalCodeDirectory, H3CellEncoder
from relay.shared.application import Clock, UnitOfWork
from relay.shared.application.health import GetHealth
from relay.shared.config import Settings
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class Container:
    """Constructor wiring. Holds long-lived objects and builds application services on demand.

    Later contexts add one `get_<service>()` method each; the api layer's
    providers call them. Nothing here is a global.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        clock: Clock | None = None,
        postal_codes: DatasetPostalCodeDirectory | None = None,
        hasher: PasswordHasher | None = None,
        tokens: TokenBroker | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.clock: Clock = clock or Clock()
        # Reads the shipped dataset on first lookup, so tests can hand in another file.
        self.postal_codes = postal_codes or DatasetPostalCodeDirectory()
        # Long-lived and stateless, so one of each for the process.
        self.hasher = hasher or auth.BcryptPasswordHasher()
        self.tokens = tokens or auth.JwtTokenBroker(settings.secret_key, self.clock)

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def auth_unit_of_work(self) -> AuthUnitOfWork:
        return auth.SqlAlchemyAuthUnitOfWork(self.session_factory)

    def get_health(self) -> GetHealth:
        return GetHealth(version=self.settings.version)

    def get_resolve_postal_code(self) -> ResolvePostalCode:
        return ResolvePostalCode(directory=self.postal_codes, cells=H3CellEncoder())

    # Auth. Every use case that writes gets one unit of work, and the token issuer
    # shares it, so an account and the session it opens land in the same transaction.

    def get_register_with_invite(self) -> RegisterWithInvite:
        uow = self.auth_unit_of_work()
        return RegisterWithInvite(
            uow=uow, hasher=self.hasher, issuer=self._issue_tokens(uow), clock=self.clock
        )

    def get_login(self) -> Login:
        uow = self.auth_unit_of_work()
        return Login(uow=uow, hasher=self.hasher, issuer=self._issue_tokens(uow))

    def get_refresh_access_token(self) -> RefreshAccessToken:
        uow = self.auth_unit_of_work()
        return RefreshAccessToken(uow=uow, issuer=self._issue_tokens(uow), clock=self.clock)

    def get_read_authenticated_user(self) -> ReadAuthenticatedUser:
        return ReadAuthenticatedUser(uow=self.auth_unit_of_work(), tokens=self.tokens)

    def get_ensure_first_admin(self) -> EnsureFirstAdmin:
        return EnsureFirstAdmin(uow=self.auth_unit_of_work(), hasher=self.hasher)

    def _issue_tokens(self, uow: AuthUnitOfWork) -> IssueTokens:
        return IssueTokens(tokens=self.tokens, clock=self.clock, uow=uow)
