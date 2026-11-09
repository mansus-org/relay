"""The five community endpoints: found one, find the ones near you, join one, read its feed."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.communities.infrastructure.models import CommunityModel
from relay.contexts.posts.infrastructure.models import PostModel
from relay.main import create_app
from relay.shared.config import Settings
from tests.fakes.clock import SteppingClock

#: Vigo and A Coruña, 154 rings apart: no community's radius reaches from one to the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
#: Three rings from Vigo — inside a 5 km community, outside a 1 km one.
NEXT_DOOR = "883920cc29fffff"
#: Forty rings out — inside a 50 km community, outside a 5 km one.
PONTEVEDRA = "883920d481fffff"
FOUNDER = UUID("11111111-1111-1111-1111-111111111111")
NEIGHBOUR = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
async def api(test_settings: Settings, migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """A client on a migrated database, on a clock that can tell two communities apart."""
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        app.state.container.clock = SteppingClock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http


def as_(who: UUID = FOUNDER) -> dict[str, str]:
    return {"Authorization": f"Bearer {who}"}


async def found(http: AsyncClient, name: str = "Vigo Book Club", **fields: object) -> dict:
    response = await http.post("/api/communities", json={"name": name, **fields}, headers=as_())
    assert response.status_code == 201, response.text
    return response.json()


async def joined(
    http: AsyncClient, community_id: str, who: UUID = FOUNDER, **fields: object
) -> dict:
    response = await http.post(
        f"/api/communities/{community_id}/join", json=fields or {}, headers=as_(who)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def say(
    http: AsyncClient,
    body: str,
    *,
    community_id: str,
    who: UUID = FOUNDER,
    location_cell: str | None = None,
) -> dict:
    payload: dict[str, object] = {"body": body, "community_id": community_id}
    if location_cell is not None:
        payload["location_cell"] = location_cell
    response = await http.post("/api/posts", json=payload, headers=as_(who))
    assert response.status_code == 201, response.text
    return response.json()


async def feed(http: AsyncClient, community_id: str, who: UUID = FOUNDER, **params: str) -> dict:
    response = await http.get(
        f"/api/communities/{community_id}/feed", params=params, headers=as_(who)
    )
    assert response.status_code == 200, response.text
    return response.json()


#: A plan has to be for a time still to come, and the clock the app reads is not this one.
NOW = datetime.now(UTC)


def at(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


async def plan(
    http: AsyncClient, title: str, *, community_id: str, who: UUID = FOUNDER, **fields: object
) -> dict:
    """A member files an event under the community they belong to."""
    response = await http.post(
        "/api/events",
        json={"title": title, "community_id": community_id, **fields},
        headers=as_(who),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def slug_of(migrated_engine: AsyncEngine, community_id: str) -> str:
    """The slug that was stored, read off the row.

    No endpoint returns a slug: nothing on either client asks for one yet, and a slug
    nobody reads is not a field to publish. It is still a unique column, so it is
    still worth a test that it was generated.
    """
    async with migrated_engine.connect() as conn:
        found = (
            await conn.execute(
                select(CommunityModel.slug).where(CommunityModel.id == UUID(community_id))
            )
        ).scalar_one()
    return str(found)


@pytest.fixture
async def club(api: AsyncClient) -> dict:
    """A community anchored in Vigo and reaching 5 km out of it, which is the usual kind."""
    return await found(api, location_cell=VIGO, radius_km=5)


@pytest.fixture
async def taken_down(api: AsyncClient, club: dict, migrated_engine: AsyncEngine) -> str:
    """A community post moderation has since removed. No endpoint can do that yet."""
    post = await say(api, "Rude, apparently.", community_id=club["id"], location_cell=VIGO)
    async with migrated_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                update(PostModel)
                .where(PostModel.id == UUID(post["id"]))
                .values(moderation_status="removed")
            )
        )
    return post["id"]


# Founding one.


async def test_founding_a_community_gives_it_back(api: AsyncClient) -> None:
    community = await found(
        api,
        "Vigo Book Club",
        description="Second Tuesday, the bakery.",
        location_cell=VIGO,
        radius_km=5,
    )

    assert community["name"] == "Vigo Book Club"
    assert community["description"] == "Second Tuesday, the bakery."
    assert community["location_cell"] == VIGO
    assert community["radius_km"] == 5.0
    assert community["member_count"] == 0
    assert community["is_member"] is False
    assert community["created_by"] == {"id": str(FOUNDER), "name": f"Member {str(FOUNDER)[:8]}"}
    # The detail screen shows "founded 3d ago", so the timestamp has to name its zone.
    assert datetime.fromisoformat(community["created_at"]).tzinfo is not None


async def test_the_slug_is_made_from_the_name(
    api: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Nothing asks for a slug and none is sent back: the server makes it from the name."""
    community = await found(api, "  O Camiño — Vigo!  ")

    assert community["name"] == "O Camiño — Vigo!"
    assert await slug_of(migrated_engine, community["id"]) == "o-camino-vigo"


async def test_a_name_with_nothing_letterlike_in_it_still_gets_a_slug(
    api: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """A slug is a unique key, so "!!!" cannot be handed the empty string every other "!!!" has."""
    first = await found(api, "!!!")
    second = await found(api, "???")

    assert await slug_of(migrated_engine, first["id"]) != ""
    assert await slug_of(migrated_engine, first["id"]) != await slug_of(
        migrated_engine, second["id"]
    )


async def test_two_towns_may_both_have_a_book_club(
    api: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Same name, different town, so neither is refused; the slugs still have to differ."""
    first = await found(api, "Book Club")
    second = await found(api, "Book Club")

    assert await slug_of(migrated_engine, first["id"]) == "book-club"
    assert await slug_of(migrated_engine, second["id"]) == f"book-club-{second['id'][:8]}"


async def test_founding_a_community_needs_someone_to_found_it(
    api: AsyncClient,
) -> None:
    for header in (None, {}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-uuid"}):
        response = await api.post("/api/communities", json={"name": "X"}, headers=header or {})
        assert response.status_code == 401


@pytest.mark.parametrize("name", ["", "   ", "a" * 81])
async def test_a_community_nobody_could_call_by_its_name_is_refused(
    api: AsyncClient, name: str
) -> None:
    assert (
        await api.post("/api/communities", json={"name": name}, headers=as_())
    ).status_code == 400


async def test_a_description_over_what_a_paragraph_is_refused(api: AsyncClient) -> None:
    assert (
        await api.post(
            "/api/communities", json={"name": "X", "description": "a" * 501}, headers=as_()
        )
    ).status_code == 400


async def test_a_community_about_a_subject_has_no_locality(api: AsyncClient) -> None:
    """No cell means no reach, and the radius the create screen always sends goes with it."""
    community = await found(api, "Long Distance Walkers", radius_km=5)

    assert community["location_cell"] is None
    assert community["radius_km"] is None


@pytest.mark.parametrize("cell", ["not-a-cell", "a" * 40])
async def test_a_community_anchored_nowhere_is_refused(api: AsyncClient, cell: str) -> None:
    """An anchor no reach test can measure from anchors nothing, so it is refused now."""
    response = await api.post(
        "/api/communities", json={"name": "X", "location_cell": cell}, headers=as_()
    )

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


@pytest.mark.parametrize("radius", [0, 0.5, 51, 500])
async def test_a_community_too_small_or_too_big_to_be_a_place_is_refused(
    api: AsyncClient, radius: float
) -> None:
    response = await api.post(
        "/api/communities",
        json={"name": "X", "location_cell": VIGO, "radius_km": radius},
        headers=as_(),
    )

    assert response.status_code == 400


# The nearby list.


async def test_the_nearby_list_is_the_communities_that_reach_where_you_are(
    api: AsyncClient, club: dict
) -> None:
    assert [c["id"] for c in (await api.get("/api/communities", params={"cell": VIGO})).json()] == [
        club["id"]
    ]
    assert (await api.get("/api/communities", params={"cell": A_CORUNA})).json() == []


async def test_a_communitys_own_radius_is_what_decides(api: AsyncClient) -> None:
    """Two communities, one anchor, different reaches: the reader is in one and not the other."""
    near = await found(api, "The Street", location_cell=VIGO, radius_km=1)
    wide = await found(api, "The Town", location_cell=VIGO, radius_km=50)

    from_next_door = [
        c["id"] for c in (await api.get("/api/communities", params={"cell": NEXT_DOOR})).json()
    ]
    from_pontevedra = [
        c["id"] for c in (await api.get("/api/communities", params={"cell": PONTEVEDRA})).json()
    ]

    assert from_next_door == [wide["id"]]
    assert from_pontevedra == [wide["id"]]
    assert near["id"] not in from_pontevedra
    assert [c["id"] for c in (await api.get("/api/communities", params={"cell": VIGO})).json()] == [
        wide["id"],
        near["id"],
    ]


async def test_a_community_about_a_subject_is_in_nobody_nearby_list(api: AsyncClient) -> None:
    await found(api, "Long Distance Walkers")

    assert (await api.get("/api/communities", params={"cell": VIGO})).json() == []


async def test_the_nearby_list_says_which_ones_you_are_already_in(
    api: AsyncClient, club: dict
) -> None:
    await joined(api, club["id"], cell=VIGO)

    listed = (await api.get("/api/communities", params={"cell": VIGO}, headers=as_(FOUNDER))).json()

    assert [(c["id"], c["is_member"], c["member_count"]) for c in listed] == [(club["id"], True, 1)]


async def test_the_nearby_list_works_for_a_stranger(api: AsyncClient, club: dict) -> None:
    """Nobody has to say who they are to see what is down their street."""
    listed = (await api.get("/api/communities", params={"cell": VIGO})).json()

    assert [(c["id"], c["is_member"]) for c in listed] == [(club["id"], False)]


async def test_the_nearby_list_needs_a_cell(api: AsyncClient) -> None:
    assert (await api.get("/api/communities")).status_code == 422


@pytest.mark.parametrize("cell", ["", "not-a-cell"])
async def test_the_nearby_list_refuses_a_cell_it_cannot_stand_in(
    api: AsyncClient, cell: str
) -> None:
    response = await api.get("/api/communities", params={"cell": cell})

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


# One community on its own.


async def test_a_community_reads_back_what_it_was_founded_as(api: AsyncClient, club: dict) -> None:
    assert (await api.get(f"/api/communities/{club['id']}")).json() == club


async def test_a_community_anybody_can_read_before_joining(api: AsyncClient, club: dict) -> None:
    """A community you cannot look at until you have joined is one you cannot decide about."""
    assert (await api.get(f"/api/communities/{club['id']}")).status_code == 200


async def test_a_community_that_was_never_founded_is_not_there(api: AsyncClient) -> None:
    assert (await api.get(f"/api/communities/{uuid4()}")).status_code == 404


async def test_an_id_that_is_not_an_id_is_not_there_either(api: AsyncClient) -> None:
    """A 404 and not a 422: the app reads a 404 as "nothing here" and carries on."""
    assert (await api.get("/api/communities/not-an-id")).status_code == 404


# Joining one.


async def test_joining_a_local_community_from_inside_it_works(api: AsyncClient, club: dict) -> None:
    community = await joined(api, club["id"], cell=VIGO)

    assert community["is_member"] is True
    assert community["member_count"] == 1


async def test_joining_a_local_community_from_outside_is_refused(
    api: AsyncClient, club: dict
) -> None:
    """The whole point of a street's community is that everyone in it is on the street."""
    response = await api.post(
        f"/api/communities/{club['id']}/join", json={"cell": A_CORUNA}, headers=as_()
    )

    assert response.status_code == 403
    assert "does not reach" in response.json()["detail"]
    unread = (await api.get(f"/api/communities/{club['id']}", headers=as_())).json()
    assert (unread["member_count"], unread["is_member"]) == (0, False)


async def test_joining_a_local_community_without_saying_where_you_are_is_refused(
    api: AsyncClient, club: dict
) -> None:
    for body in ({}, {"cell": None}):
        response = await api.post(f"/api/communities/{club['id']}/join", json=body, headers=as_())
        assert response.status_code == 403


async def test_joining_a_community_about_a_subject_needs_no_cell(api: AsyncClient) -> None:
    walkers = await found(api, "Long Distance Walkers")

    assert (await joined(api, walkers["id"]))["is_member"] is True


async def test_joining_a_community_you_are_already_in_is_the_same_button_twice(
    api: AsyncClient, club: dict
) -> None:
    await joined(api, club["id"], cell=VIGO)

    again = await joined(api, club["id"], cell=VIGO)

    assert again["member_count"] == 1


async def test_joining_needs_someone_to_join_as(api: AsyncClient, club: dict) -> None:
    response = await api.post(f"/api/communities/{club['id']}/join", json={"cell": VIGO})

    assert response.status_code == 401


async def test_joining_a_community_that_was_never_founded_is_not_there(api: AsyncClient) -> None:
    assert (
        await api.post(f"/api/communities/{uuid4()}/join", json={"cell": VIGO}, headers=as_())
    ).status_code == 404


async def test_joining_from_a_cell_that_is_not_a_cell_is_refused(
    api: AsyncClient, club: dict
) -> None:
    response = await api.post(
        f"/api/communities/{club['id']}/join", json={"cell": "not-a-cell"}, headers=as_()
    )

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


# A community's feed.


async def test_a_community_feed_is_for_its_members(api: AsyncClient, club: dict) -> None:
    response = await api.get(f"/api/communities/{club['id']}/feed", headers=as_())

    assert response.status_code == 403
    assert "Only members" in response.json()["detail"]

    await joined(api, club["id"], cell=VIGO)
    assert (await api.get(f"/api/communities/{club['id']}/feed", headers=as_())).status_code == 200


async def test_a_stranger_with_no_token_at_all_is_not_a_member(
    api: AsyncClient, club: dict
) -> None:
    assert (await api.get(f"/api/communities/{club['id']}/feed")).status_code == 403


async def test_a_community_feed_is_newest_first(api: AsyncClient, club: dict) -> None:
    await joined(api, club["id"], cell=VIGO)
    await say(api, "older", community_id=club["id"])
    await say(api, "newer", community_id=club["id"])

    assert [post["body"] for post in (await feed(api, club["id"]))["posts"]] == ["newer", "older"]


async def test_a_community_feed_shows_its_posts_wherever_they_were_said(api: AsyncClient) -> None:
    """No locality filter at read time: joining is where the distance was already checked."""
    club = await found(api, location_cell=VIGO, radius_km=5)
    await joined(api, club["id"], cell=VIGO)
    await say(api, "said at home", community_id=club["id"], location_cell=VIGO)
    await say(api, "said on holiday", community_id=club["id"], location_cell=A_CORUNA)
    await say(api, "said nowhere", community_id=club["id"])

    assert [post["body"] for post in (await feed(api, club["id"]))["posts"]] == [
        "said nowhere",
        "said on holiday",
        "said at home",
    ]


async def test_a_post_of_another_community_is_not_in_this_one(api: AsyncClient, club: dict) -> None:
    await joined(api, club["id"], cell=VIGO)
    await say(api, "elsewhere", community_id=str(uuid4()))

    assert (await feed(api, club["id"]))["posts"] == []


async def test_a_post_taken_down_is_out_of_a_community_feed(
    api: AsyncClient, club: dict, taken_down: str
) -> None:
    await joined(api, club["id"], cell=VIGO)
    await say(api, "still here", community_id=club["id"])

    bodies = [post["body"] for post in (await feed(api, club["id"]))["posts"]]

    assert bodies == ["still here"]


async def test_a_member_who_joined_under_a_pseudonym_is_called_by_it(api: AsyncClient) -> None:
    """The name beside their post is what this community calls them, and nowhere else."""
    club = await found(api, allow_pseudonyms=True, location_cell=VIGO, radius_km=5)
    await joined(api, club["id"], who=NEIGHBOUR, cell=VIGO, pseudonym="the baker")
    post = await say(
        api, "Bread at six.", community_id=club["id"], who=NEIGHBOUR, location_cell=VIGO
    )
    await joined(api, club["id"], cell=VIGO)

    entry = (await feed(api, club["id"]))["posts"][0]

    assert entry["id"] == post["id"]
    assert entry["author"] == {"id": str(NEIGHBOUR), "name": "the baker"}
    # The same post in the street is still said by a member, not by a baker.
    street = (await api.get("/api/feed", params={"cell": VIGO})).json()["posts"][0]
    assert street["author"] == {"id": str(NEIGHBOUR), "name": f"Member {str(NEIGHBOUR)[:8]}"}


async def test_a_member_without_a_pseudonym_is_called_by_their_own_name(
    api: AsyncClient, club: dict
) -> None:
    await joined(api, club["id"], cell=VIGO)
    await say(api, "Normal person here.", community_id=club["id"])

    assert (await feed(api, club["id"]))["posts"][0]["author"]["name"] == (
        f"Member {str(FOUNDER)[:8]}"
    )


async def test_a_pseudonym_where_they_are_not_allowed_is_refused(
    api: AsyncClient, club: dict
) -> None:
    """Asking not to be named and being named anyway is worse than an error."""
    response = await api.post(
        f"/api/communities/{club['id']}/join",
        json={"cell": VIGO, "pseudonym": "the baker"},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "does not let members use a pseudonym" in response.json()["detail"]


async def test_a_pseudonym_over_what_fits_next_to_a_post_is_refused(api: AsyncClient) -> None:
    club = await found(api, allow_pseudonyms=True)

    response = await api.post(
        f"/api/communities/{club['id']}/join",
        json={"pseudonym": "a" * 41},
        headers=as_(),
    )

    assert response.status_code == 400


async def test_joining_twice_keeps_the_pseudonym_you_first_used(api: AsyncClient) -> None:
    """Changing what you are called here is not what pressing Join means again."""
    club = await found(api, allow_pseudonyms=True)

    await joined(api, club["id"], who=NEIGHBOUR, pseudonym="the baker")
    again = await joined(api, club["id"], who=NEIGHBOUR, pseudonym="the liar")
    await joined(api, club["id"])
    await say(api, "Bread at six.", community_id=club["id"], who=NEIGHBOUR)

    assert again["member_count"] == 1
    assert (await feed(api, club["id"]))["posts"][0]["author"]["name"] == "the baker"


async def test_a_community_feed_pages_and_says_where_the_next_page_starts(
    api: AsyncClient, club: dict
) -> None:
    await joined(api, club["id"], cell=VIGO)
    for index in range(25):
        await say(api, f"post {index}", community_id=club["id"])

    first = await feed(api, club["id"])
    assert len(first["posts"]) == 20
    assert first["next_cursor"] is not None
    # A `+` in a query string arrives as a space, which is no longer a timestamp.
    assert "+" not in first["next_cursor"]

    second = await feed(api, club["id"], cursor=first["next_cursor"])

    assert [post["body"] for post in second["posts"]] == [f"post {n}" for n in range(4, -1, -1)]
    assert second["next_cursor"] is None
    seen = [post["id"] for post in first["posts"] + second["posts"]]
    assert len(set(seen)) == 25


@pytest.mark.parametrize("cursor", ["yesterday", ""])
async def test_a_cursor_this_feed_never_handed_out_is_refused(
    api: AsyncClient, club: dict, cursor: str
) -> None:
    await joined(api, club["id"], cell=VIGO)

    assert (
        await api.get(
            f"/api/communities/{club['id']}/feed", params={"cursor": cursor}, headers=as_()
        )
    ).status_code == 400


async def test_the_feed_of_a_community_that_was_never_founded_is_not_there(
    api: AsyncClient,
) -> None:
    assert (await api.get(f"/api/communities/{uuid4()}/feed", headers=as_())).status_code == 404


# The community's events, beside its posts.


async def test_a_communitys_events_are_on_its_feed_beside_its_posts(
    api: AsyncClient, club: dict
) -> None:
    """A plan is an announcement, so it is on the feed with whatever announced it.

    Two lists and not one: a post is paged by when it was written and a plan by when it
    happens, and the two clocks cannot share a cursor.
    """
    await joined(api, club["id"], cell=VIGO)
    await say(api, "Anyone re-reading The Dispossessed?", community_id=club["id"])
    await plan(api, "Book swap", community_id=club["id"], location_cell=VIGO, starts_at=at(24))

    page = await feed(api, club["id"], cell=VIGO)

    assert [post["body"] for post in page["posts"]] == ["Anyone re-reading The Dispossessed?"]
    assert [event["title"] for event in page["events"]] == ["Book swap"]
    assert page["events"][0]["community_id"] == club["id"]


async def test_a_feed_asked_without_a_cell_says_nothing_about_events(
    api: AsyncClient, club: dict
) -> None:
    """No place to stand, nothing you could get to. The posts are not held back for it."""
    await joined(api, club["id"], cell=VIGO)
    await say(api, "Book swap on Thursday.", community_id=club["id"])
    await plan(api, "Book swap", community_id=club["id"], location_cell=VIGO, starts_at=at(24))

    page = await feed(api, club["id"])

    assert page["events"] == []
    assert len(page["posts"]) == 1


async def test_an_event_outside_the_readers_reach_is_not_announced_to_them(
    api: AsyncClient, club: dict
) -> None:
    """The member who filed it is not shown a plan they cannot walk to.

    The club is Vigo at 5 km and the plan is A Coruña, some 170 km off. Membership is
    what lets a member file a plan, never what lets them see one — the ticket's locality
    rule, and the feed is not a second door around it.
    """
    await joined(api, club["id"], cell=VIGO)
    await plan(
        api,
        "Reading in A Coruña",
        community_id=club["id"],
        location_cell=A_CORUNA,
        starts_at=at(24),
    )

    assert (await feed(api, club["id"], cell=VIGO))["events"] == []


async def test_an_event_with_no_place_yet_is_not_announced(api: AsyncClient, club: dict) -> None:
    """A plan nobody has given a place is in nobody's reach, so it is in nobody's feed."""
    await joined(api, club["id"], cell=VIGO)
    await plan(api, "Venue to be confirmed", community_id=club["id"], starts_at=at(24))

    assert (await feed(api, club["id"], cell=VIGO))["events"] == []


async def test_the_feed_leads_with_what_the_community_last_filed(
    api: AsyncClient, club: dict
) -> None:
    """Newest filed first, which is the opposite way round from the calendar.

    "tonight" was put up first and happens first; "next month" was put up second. A feed
    of posts leads with what is new, and a plan that is a month off but filed five seconds
    ago is the new thing here.
    """
    await joined(api, club["id"], cell=VIGO)
    await plan(api, "tonight", community_id=club["id"], location_cell=VIGO, starts_at=at(3))
    await plan(
        api, "next month", community_id=club["id"], location_cell=VIGO, starts_at=at(24 * 30)
    )

    assert [event["title"] for event in (await feed(api, club["id"], cell=VIGO))["events"]] == [
        "next month",
        "tonight",
    ]


async def test_a_feed_is_a_glance_and_the_calendar_is_the_scroll(
    api: AsyncClient, club: dict
) -> None:
    """Ten is where the feed stops, and the community's own list keeps going past it."""
    await joined(api, club["id"], cell=VIGO)
    for index in range(12):
        await plan(
            api, f"event {index}", community_id=club["id"], location_cell=VIGO, starts_at=at(24)
        )

    assert len((await feed(api, club["id"], cell=VIGO))["events"]) == 10
    listed = await api.get(f"/api/communities/{club['id']}/events", params={"cell": VIGO})

    assert len(listed.json()["events"]) == 12


async def test_a_stranger_asking_after_events_is_still_not_a_member(
    api: AsyncClient, club: dict
) -> None:
    """The posts are read first, and they are what say whether this reader may be here."""
    await joined(api, club["id"], NEIGHBOUR, cell=VIGO)
    await plan(
        api,
        "Book swap",
        community_id=club["id"],
        who=NEIGHBOUR,
        location_cell=VIGO,
        starts_at=at(24),
    )

    assert (
        await api.get(f"/api/communities/{club['id']}/feed", params={"cell": VIGO})
    ).status_code == 403


async def test_a_cell_that_is_not_a_cell_is_refused(api: AsyncClient, club: dict) -> None:
    await joined(api, club["id"], cell=VIGO)

    response = await api.get(
        f"/api/communities/{club['id']}/feed", params={"cell": "not-a-cell"}, headers=as_()
    )

    assert response.status_code == 400


# The shapes the mobile client already reads, field for field.


async def test_the_community_shape_is_the_one_the_mobile_client_parses(
    api: AsyncClient, club: dict
) -> None:
    assert set(club) == {
        "id",
        "name",
        "description",
        "member_count",
        "location_cell",
        "radius_km",
        "allow_pseudonyms",
        "is_member",
        "created_by",
        "created_at",
    }
    assert set(club["created_by"]) == {"id", "name"}


async def test_the_community_post_shape_is_a_post_shape(api: AsyncClient, club: dict) -> None:
    await joined(api, club["id"], cell=VIGO)
    await say(api, "Shape check.", community_id=club["id"], location_cell=VIGO)

    entry = (await feed(api, club["id"]))["posts"][0]

    assert set(entry) >= {"id", "author", "body", "created_at"}
    assert set(entry["author"]) == {"id", "name"}


async def test_every_community_endpoint_is_in_the_openapi_document(api: AsyncClient) -> None:
    paths = (await api.get("/openapi.json")).json()["paths"]

    assert {
        "/api/communities",
        "/api/communities/{community_id}",
        "/api/communities/{community_id}/feed",
        "/api/communities/{community_id}/join",
    } <= set(paths)
