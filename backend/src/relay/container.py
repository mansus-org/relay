from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.communities.application import (
    CommunitiesUnitOfWork,
    CreateCommunity,
    GetCommunity,
    GetCommunityFeed,
    JoinCommunity,
    ListCommunities,
)
from relay.contexts.communities.infrastructure import (
    H3CommunityReach,
    SqlAlchemyCommunitiesUnitOfWork,
)
from relay.contexts.location.application import ResolvePostalCode
from relay.contexts.location.infrastructure import DatasetPostalCodeDirectory, H3CellEncoder
from relay.contexts.posts.application import CreatePost, GetFeed, GetPost, PostsUnitOfWork
from relay.contexts.posts.infrastructure import (
    H3CellNeighbourhood,
    H3CellStandard,
    SqlAlchemyPostsUnitOfWork,
)
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
        neighbourhood: H3CellNeighbourhood | None = None,
        cells: H3CellStandard | None = None,
        reach: H3CommunityReach | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.clock: Clock = clock or Clock()
        # Reads the shipped dataset on first lookup, so tests can hand in another file.
        self.postal_codes = postal_codes or DatasetPostalCodeDirectory()
        # How far a feed reaches, in cells. Same cut the client sends its cell with.
        self.neighbourhood = neighbourhood or H3CellNeighbourhood()
        # What counts as a cell at all, so nothing is filed where no feed will look.
        self.cells = cells or H3CellStandard()
        # Whether one community's radius reaches a given cell. Same cut again.
        self.reach = reach or H3CommunityReach()

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def posts_unit_of_work(self) -> PostsUnitOfWork:
        return SqlAlchemyPostsUnitOfWork(self.session_factory)

    def communities_unit_of_work(self) -> CommunitiesUnitOfWork:
        return SqlAlchemyCommunitiesUnitOfWork(self.session_factory)

    def get_health(self) -> GetHealth:
        return GetHealth(version=self.settings.version)

    def get_resolve_postal_code(self) -> ResolvePostalCode:
        return ResolvePostalCode(directory=self.postal_codes, cells=H3CellEncoder())

    def get_create_post(self) -> CreatePost:
        return CreatePost(uow=self.posts_unit_of_work(), clock=self.clock, cells=self.cells)

    def get_feed(self) -> GetFeed:
        return GetFeed(uow=self.posts_unit_of_work(), neighbourhood=self.neighbourhood)

    def get_post(self) -> GetPost:
        return GetPost(uow=self.posts_unit_of_work())

    def get_create_community(self) -> CreateCommunity:
        return CreateCommunity(
            uow=self.communities_unit_of_work(), clock=self.clock, cells=self.cells
        )

    def get_list_communities(self) -> ListCommunities:
        return ListCommunities(
            uow=self.communities_unit_of_work(), cells=self.cells, reach=self.reach
        )

    def get_community(self) -> GetCommunity:
        return GetCommunity(uow=self.communities_unit_of_work())

    def get_community_feed(self) -> GetCommunityFeed:
        return GetCommunityFeed(uow=self.communities_unit_of_work())

    def get_join_community(self) -> JoinCommunity:
        return JoinCommunity(
            uow=self.communities_unit_of_work(),
            clock=self.clock,
            cells=self.cells,
            reach=self.reach,
        )
