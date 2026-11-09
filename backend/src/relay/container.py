from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.admin.application import (
    DeactivateMember,
    GetMember,
    IssueInvite,
    ListInvites,
    ListMembers,
    ModerationQueue,
    ModerationUnitOfWork,
    ReadModerationLog,
    ReadPost,
    RestoreMember,
    ReviewPost,
    RevokeInvite,
)
from relay.contexts.admin.infrastructure.unit_of_work import SqlAlchemyModerationUnitOfWork
from relay.contexts.auth import infrastructure as auth
from relay.contexts.auth.application import (
    EnsureFirstAdmin,
    IssueTokens,
    Login,
    ReadAuthenticatedUser,
    RefreshAccessToken,
    RegisterWithInvite,
    UpdateDisplayName,
)
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.ports import PasswordHasher, TokenBroker
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
from relay.contexts.events.application import (
    CancelRsvp,
    CreateEvent,
    EventsUnitOfWork,
    GetEvent,
    GetEvents,
    RsvpEvent,
)
from relay.contexts.events.infrastructure import (
    EventsCellNeighbourhood,
    EventsCellStandard,
    SqlAlchemyEventsUnitOfWork,
)
from relay.contexts.location.application import ResolvePostalCode
from relay.contexts.location.infrastructure import DatasetPostalCodeDirectory, H3CellEncoder
from relay.contexts.posts.application import (
    AddReaction,
    CreatePost,
    GetFeed,
    GetPost,
    GetReplies,
    GetTallies,
    PostsUnitOfWork,
    RemoveReaction,
)
from relay.contexts.posts.infrastructure import (
    H3CellNeighbourhood,
    H3CellStandard,
    LocalBroadcaster,
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
        hasher: PasswordHasher | None = None,
        tokens: TokenBroker | None = None,
        neighbourhood: H3CellNeighbourhood | None = None,
        cells: H3CellStandard | None = None,
        reach: H3CommunityReach | None = None,
        events_neighbourhood: EventsCellNeighbourhood | None = None,
        events_cells: EventsCellStandard | None = None,
        live_feed: LocalBroadcaster | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.clock: Clock = clock or Clock()
        # Reads the shipped dataset on first lookup, so tests can hand in another file.
        self.postal_codes = postal_codes or DatasetPostalCodeDirectory()
        # Long-lived and stateless, so one of each for the process.
        self.hasher = hasher or auth.BcryptPasswordHasher()
        self.tokens = tokens or auth.JwtTokenBroker(settings.secret_key, self.clock)
        # How far a feed reaches, in cells. Same cut the client sends its cell with.
        self.neighbourhood = neighbourhood or H3CellNeighbourhood()
        # What counts as a cell at all, so nothing is filed where no feed will look.
        self.cells = cells or H3CellStandard()
        # Whether one community's radius reaches a given cell. Same cut again.
        self.reach = reach or H3CommunityReach()
        # The events context asks H3 the same two questions and answers them itself,
        # so that changing how far a feed reaches is never also a change to what is on.
        self.events_neighbourhood = events_neighbourhood or EventsCellNeighbourhood()
        self.events_cells = events_cells or EventsCellStandard()
        # Who is reading a locality right now, in this process. One for the process, so
        # the write that makes a post and the stream that carries it agree on the cells.
        self.live_feed = live_feed or LocalBroadcaster(self.neighbourhood)

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def auth_unit_of_work(self) -> AuthUnitOfWork:
        return auth.SqlAlchemyAuthUnitOfWork(self.session_factory)

    def posts_unit_of_work(self) -> PostsUnitOfWork:
        return SqlAlchemyPostsUnitOfWork(self.session_factory)

    def communities_unit_of_work(self) -> CommunitiesUnitOfWork:
        return SqlAlchemyCommunitiesUnitOfWork(self.session_factory)

    def events_unit_of_work(self) -> EventsUnitOfWork:
        return SqlAlchemyEventsUnitOfWork(self.session_factory)

    def moderation_unit_of_work(self) -> ModerationUnitOfWork:
        return SqlAlchemyModerationUnitOfWork(self.session_factory)

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

    def get_update_display_name(self) -> UpdateDisplayName:
        return UpdateDisplayName(uow=self.auth_unit_of_work())

    def _issue_tokens(self, uow: AuthUnitOfWork) -> IssueTokens:
        return IssueTokens(tokens=self.tokens, clock=self.clock, uow=uow)

    # Moderation. One unit of work for the whole admin surface, because every write in it
    # has to land next to its line in the trail: a decision nobody wrote down is a decision
    # nobody can be asked about afterwards.

    def get_moderation_queue(self) -> ModerationQueue:
        return ModerationQueue(self.moderation_unit_of_work())

    def get_moderated_post(self) -> ReadPost:
        return ReadPost(self.moderation_unit_of_work())

    def get_review_post(self) -> ReviewPost:
        return ReviewPost(self.moderation_unit_of_work(), self.clock)

    def get_moderation_log(self) -> ReadModerationLog:
        return ReadModerationLog(self.moderation_unit_of_work())

    def get_list_members(self) -> ListMembers:
        return ListMembers(self.moderation_unit_of_work())

    def get_get_member(self) -> GetMember:
        return GetMember(self.moderation_unit_of_work())

    def get_deactivate_member(self) -> DeactivateMember:
        return DeactivateMember(self.moderation_unit_of_work(), self.clock)

    def get_restore_member(self) -> RestoreMember:
        return RestoreMember(self.moderation_unit_of_work(), self.clock)

    def get_list_invites(self) -> ListInvites:
        return ListInvites(self.moderation_unit_of_work())

    def get_issue_invite(self) -> IssueInvite:
        return IssueInvite(self.moderation_unit_of_work(), self.clock)

    def get_revoke_invite(self) -> RevokeInvite:
        return RevokeInvite(self.moderation_unit_of_work(), self.clock)

    def get_create_post(self) -> CreatePost:
        return CreatePost(
            uow=self.posts_unit_of_work(),
            clock=self.clock,
            cells=self.cells,
            live_feed=self.live_feed,
        )

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

    def get_create_event(self) -> CreateEvent:
        return CreateEvent(
            uow=self.events_unit_of_work(), clock=self.clock, cells=self.events_cells
        )

    def get_events(self) -> GetEvents:
        return GetEvents(
            uow=self.events_unit_of_work(),
            neighbourhood=self.events_neighbourhood,
            clock=self.clock,
        )

    def get_event(self) -> GetEvent:
        return GetEvent(uow=self.events_unit_of_work())

    def get_rsvp_event(self) -> RsvpEvent:
        return RsvpEvent(uow=self.events_unit_of_work(), clock=self.clock)

    def get_cancel_rsvp(self) -> CancelRsvp:
        return CancelRsvp(uow=self.events_unit_of_work())

    def get_replies(self) -> GetReplies:
        return GetReplies(uow=self.posts_unit_of_work())

    def get_tallies(self) -> GetTallies:
        return GetTallies(uow=self.posts_unit_of_work())

    def get_add_reaction(self) -> AddReaction:
        return AddReaction(uow=self.posts_unit_of_work(), clock=self.clock)

    def get_remove_reaction(self) -> RemoveReaction:
        return RemoveReaction(uow=self.posts_unit_of_work())
