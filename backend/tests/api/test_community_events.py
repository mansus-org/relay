"""Events that belong to a community: put one on a group's list, read that list back."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.main import create_app
from relay.shared.config import Settings

#: Vigo and A Coruña, about 170 km apart: neither one's locality sees the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
FOUNDER = UUID("11111111-1111-1111-1111-111111111111")
MEMBER = UUID("22222222-2222-2222-2222-222222222222")
STRANGER = UUID("33333333-3333-3333-3333-333333333333")

NOW = datetime.now(UTC)


@pytest.fixture
async def api(test_settings: Settings, migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as http,
    ):
        yield http


def as_(who: UUID = FOUNDER) -> dict[str, str]:
    return {"Authorization": f"Bearer {who}"}


def at(hours: float) -> str:
    """A time `hours` from now, so "still to come" stays true however long the suite runs."""
    return (NOW + timedelta(hours=hours)).isoformat()


async def found(http: AsyncClient, name: str = "Vigo Book Club", **fields: object) -> dict:
    """A community to file under. No cell, so it is about a subject and anyone can join it."""
    response = await http.post("/api/communities", json={"name": name, **fields}, headers=as_())
    assert response.status_code == 201, response.text
    return response.json()


async def joined(http: AsyncClient, community_id: str, who: UUID) -> None:
    response = await http.post(f"/api/communities/{community_id}/join", json={}, headers=as_(who))
    assert response.status_code == 200, response.text


async def plan(http: AsyncClient, title: str, who: UUID = FOUNDER, **fields: object) -> dict:
    response = await http.post("/api/events", json={"title": title, **fields}, headers=as_(who))
    assert response.status_code == 201, response.text
    return response.json()


async def on(http: AsyncClient, community_id: str, **params: str) -> dict:
    """Read a community's list from Vigo, unless the test says otherwise."""
    response = await http.get(
        f"/api/communities/{community_id}/events", params={"cell": VIGO, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()


# Putting one on the list.


async def test_a_member_can_plan_an_event_for_the_community_they_belong_to(
    api: AsyncClient,
) -> None:
    club = await found(api)
    await joined(api, club["id"], MEMBER)

    event = await plan(api, "Book swap", who=MEMBER, community_id=club["id"], starts_at=at(24))

    assert event["community_id"] == club["id"]


async def test_the_event_appears_on_that_communitys_list(api: AsyncClient) -> None:
    club = await found(api)
    await joined(api, club["id"], FOUNDER)

    await plan(api, "Book swap", community_id=club["id"], location_cell=VIGO, starts_at=at(24))
    page = await on(api, club["id"])

    assert [event["title"] for event in page["events"]] == ["Book swap"]
    assert page["events"][0]["community_name"] == "Vigo Book Club"


async def test_an_event_with_no_community_on_it_is_on_nobody_s_list(api: AsyncClient) -> None:
    """The old shape of an event still plans, and stays off every community's list."""
    club = await found(api)
    await joined(api, club["id"], FOUNDER)

    await plan(api, "Just a place", location_cell=VIGO, starts_at=at(24))
    page = await on(api, club["id"])

    assert page["events"] == []


async def test_a_stranger_cannot_put_an_event_on_a_communitys_list(api: AsyncClient) -> None:
    """Reading a community's list is public; writing to it is what membership buys."""
    club = await found(api)

    response = await api.post(
        "/api/events",
        json={"title": "Not ours", "starts_at": at(24), "community_id": club["id"]},
        headers=as_(STRANGER),
    )

    assert response.status_code == 403
    assert (await on(api, club["id"]))["events"] == []


async def test_an_event_filed_under_a_community_that_does_not_exist_is_refused(
    api: AsyncClient,
) -> None:
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(24), "community_id": str(uuid4())},
        headers=as_(FOUNDER),
    )

    assert response.status_code == 404


# Reading one.


async def test_the_list_is_public(api: AsyncClient) -> None:
    """No token, and the community's plans still show: an event is a public thing."""
    club = await found(api)
    await joined(api, club["id"], FOUNDER)
    await plan(api, "Book swap", community_id=club["id"], location_cell=VIGO, starts_at=at(24))

    response = await api.get(f"/api/communities/{club['id']}/events", params={"cell": VIGO})

    assert response.status_code == 200
    assert [event["title"] for event in response.json()["events"]] == ["Book swap"]


async def test_one_communitys_list_does_not_show_anothers(api: AsyncClient) -> None:
    club = await found(api, "Vigo Book Club")
    choir = await found(api, "The Choir")
    await joined(api, club["id"], FOUNDER)
    await joined(api, choir["id"], FOUNDER)

    await plan(api, "Book swap", community_id=club["id"], location_cell=VIGO, starts_at=at(24))
    await plan(api, "Rehearsal", community_id=choir["id"], location_cell=VIGO, starts_at=at(48))

    assert [event["title"] for event in (await on(api, club["id"]))["events"]] == ["Book swap"]
    assert [event["title"] for event in (await on(api, choir["id"]))["events"]] == ["Rehearsal"]


async def test_the_next_event_is_first(api: AsyncClient) -> None:
    club = await found(api)
    await joined(api, club["id"], FOUNDER)

    await plan(api, "Later", community_id=club["id"], location_cell=VIGO, starts_at=at(48))
    await plan(api, "Sooner", community_id=club["id"], location_cell=VIGO, starts_at=at(24))
    page = await on(api, club["id"])

    assert [event["title"] for event in page["events"]] == ["Sooner", "Later"]


async def test_an_event_that_already_started_is_not_on_the_list(api: AsyncClient) -> None:
    club = await found(api)
    await joined(api, club["id"], FOUNDER)

    await plan(api, "Last week", community_id=club["id"], location_cell=VIGO, starts_at=at(-24 * 7))
    await plan(api, "Tomorrow", community_id=club["id"], location_cell=VIGO, starts_at=at(24))

    page = await on(api, club["id"])
    assert [event["title"] for event in page["events"]] == ["Tomorrow"]

    past = await on(api, club["id"], **{"from": "past"})
    assert [event["title"] for event in past["events"]] == ["Last week"]


async def test_the_ring_applies_to_a_communitys_list_like_any_other(api: AsyncClient) -> None:
    """Membership is what lets you file an event, never what lets you see one.

    A Coruña and Vigo are ~170 km apart, so the member standing in Vigo does not get
    told about the ride A Coruña is throwing, however much they are in the club that is
    throwing it — and the plan with no place on it is on no list at all, because an event
    is visible where its cell is.
    """
    club = await found(api)
    await joined(api, club["id"], FOUNDER)

    await plan(api, "Down the road", community_id=club["id"], location_cell=VIGO, starts_at=at(24))
    await plan(
        api, "Up the coast", community_id=club["id"], location_cell=A_CORUNA, starts_at=at(25)
    )
    await plan(api, "No venue yet", community_id=club["id"], starts_at=at(26))

    from_vigo = await on(api, club["id"])
    assert [event["title"] for event in from_vigo["events"]] == ["Down the road"]

    from_coruna = await on(api, club["id"], cell=A_CORUNA)
    assert [event["title"] for event in from_coruna["events"]] == ["Up the coast"]


async def test_the_pages_walk_without_gaps_or_repeats(api: AsyncClient) -> None:
    club = await found(api)
    await joined(api, club["id"], FOUNDER)
    for index in range(25):
        await plan(
            api,
            f"event {index}",
            community_id=club["id"],
            location_cell=VIGO,
            starts_at=at(index + 1),
        )

    first = await on(api, club["id"])
    assert len(first["events"]) == 20
    assert first["next_from"] is not None

    second = await on(api, club["id"], **{"from": first["next_from"]})
    seen = [event["title"] for event in first["events"] + second["events"]]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert second["next_from"] is None


async def test_a_community_that_does_not_exist_has_no_list(api: AsyncClient) -> None:
    """Not an empty list: a community that was never founded is a different answer."""
    response = await api.get(f"/api/communities/{uuid4()}/events", params={"cell": VIGO})

    assert response.status_code == 404


async def test_a_start_that_is_not_a_start_is_refused(api: AsyncClient) -> None:
    club = await found(api)

    response = await api.get(
        f"/api/communities/{club['id']}/events",
        params={"cell": VIGO, "from": "whenever the rain stops"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("cell", ["", "not-a-cell"])
async def test_the_community_list_refuses_a_cell_it_cannot_read(
    api: AsyncClient, cell: str
) -> None:
    """A cell nobody can resolve is a bad question here too, not an empty page."""
    club = await found(api)

    response = await api.get(f"/api/communities/{club['id']}/events", params={"cell": cell})

    assert response.status_code == 400
