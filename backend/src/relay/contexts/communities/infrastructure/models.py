"""The communities and community_members tables. These models never leave infrastructure."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.communities.domain.community import Community
from relay.contexts.communities.domain.membership import Membership
from relay.shared.infrastructure.database import Base


def _as_utc(value: datetime) -> datetime:
    """SQLite stores no offset, so a timestamp read back is naive and UTC by agreement.

    Postgres keeps the offset in `timestamptz` and hands back an aware datetime, so
    this is a no-op there. Copied from the posts context rather than shared, because
    neither context owns `shared` and both need it.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CommunityModel(Base):
    """One community.

    `member_count` and `is_member` are not columns: they are read out of
    `community_members` by whichever query needed them, and are absent here.
    """

    __tablename__ = "communities"
    # Two towns are entitled to a community called Book Club; two rows answering to the
    # same slug are not, because a slug is how something gets found.
    __table_args__ = (UniqueConstraint("slug"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location_cell: Mapped[str | None] = mapped_column(String(32))
    radius_km: Mapped[float | None] = mapped_column(Float)
    allow_pseudonyms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, community: Community) -> "CommunityModel":
        return cls(
            id=community.id,
            name=community.name,
            slug=community.slug,
            description=community.description,
            location_cell=community.location_cell,
            radius_km=community.radius_km,
            allow_pseudonyms=community.allow_pseudonyms,
            created_by=community.created_by,
            created_at=community.created_at.astimezone(UTC),
        )

    def to_domain(self, *, member_count: int = 0, is_member: bool = False) -> Community:
        return Community(
            id=self.id,
            name=self.name,
            slug=self.slug,
            description=self.description,
            location_cell=self.location_cell,
            radius_km=self.radius_km,
            allow_pseudonyms=self.allow_pseudonyms,
            created_by=self.created_by,
            created_at=_as_utc(self.created_at),
            member_count=member_count,
            is_member=is_member,
        )


class CommunityMemberModel(Base):
    """One membership: a person, a community, and what they are called there.

    The unique pair is the rule, not an optimisation: a person is one member of a
    community, and a second row for them would be counted twice and joined from twice.
    """

    __tablename__ = "community_members"
    __table_args__ = (UniqueConstraint("community_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    community_id: Mapped[UUID] = mapped_column(ForeignKey("communities.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    pseudonym: Mapped[str | None] = mapped_column(String(40))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, membership: Membership) -> "CommunityMemberModel":
        return cls(
            id=membership.id,
            community_id=membership.community_id,
            user_id=membership.user_id,
            pseudonym=membership.pseudonym,
            joined_at=membership.joined_at.astimezone(UTC),
        )

    def to_domain(self) -> Membership:
        return Membership(
            id=self.id,
            community_id=self.community_id,
            user_id=self.user_id,
            pseudonym=self.pseudonym,
            joined_at=_as_utc(self.joined_at),
        )
