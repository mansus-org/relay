from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.clock: Clock = clock or Clock()
        # Reads the shipped dataset on first lookup, so tests can hand in another file.
        self.postal_codes = postal_codes or DatasetPostalCodeDirectory()

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def get_health(self) -> GetHealth:
        return GetHealth(version=self.settings.version)

    def get_resolve_postal_code(self) -> ResolvePostalCode:
        return ResolvePostalCode(directory=self.postal_codes, cells=H3CellEncoder())
