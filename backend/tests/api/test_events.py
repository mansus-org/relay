"""The endpoints a person uses to plan something, find it, and say they are coming."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import h3
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.main import create_app
from relay.shared.config import Settings

#: Vigo and A Coruña, about 170 km apart: far enough that neither locality sees the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
HOST = UUID("11111111-1111-1111-1111-111111111111")
TOKYO = timezone(timedelta(hours=9))

#: The moment the tests are run: every event is planned relative to it, so the list of
#: what is still to come stays a list of what is still to come however long they sit.
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


def as_(member: UUID = HOST) -> dict[str, str]:
    return {"Authorization": f"Bearer {member}"}


def at(hours: float) -> str:
    """A time `hours` from now, written the way a phone writes one: with its zone on it."""
    return (NOW + timedelta(hours=hours)).isoformat()


async def plan(http: AsyncClient, title: str, **fields: object) -> dict:
    response = await http.post("/api/events", json={"title": title, **fields}, headers=as_())
    assert response.status_code == 201, response.text
    return response.json()


async def on(http: AsyncClient, cell: str = VIGO) -> dict:
    response = await http.get("/api/events", params={"cell": cell})
    assert response.status_code == 200, response.text
    return response.json()


# Planning.


async def test_planning_an_event_gives_it_back(api: AsyncClient) -> None:
    event = await plan(
        api,
        "Book swap",
        starts_at=at(24),
        ends_at=at(26),
        venue_name="The corner bar",
        details="Bring one book.",
        location_cell=VIGO,
    )

    assert event["title"] == "Book swap"
    assert event["host_id"] == str(HOST)
    assert event["host_name"] == f"Member {str(HOST)[:8]}"
    assert event["venue_name"] == "The corner bar"
    assert event["details"] == "Bring one book."
    assert event["location_cell"] == VIGO
    assert event["rsvp_count"] == 0
    assert UUID(event["id"]) != HOST
    # A phone renders the start time, so it has to name the zone it is in.
    assert datetime.fromisoformat(event["starts_at"]).tzinfo is not None


async def test_an_event_can_be_planned_without_saying_where_or_when_it_ends(
    api: AsyncClient,
) -> None:
    """A plan whose place is not settled yet is still a plan."""
    event = await plan(api, "Something, eventually", starts_at=at(48))

    assert event["location_cell"] is None
    assert event["ends_at"] is None
    assert event["details"] is None


async def test_a_time_that_names_no_zone_is_refused(api: AsyncClient) -> None:
    """`2030-01-01T18:00:00` is a wall clock that never says whose.

    Read as the server's zone it files a supper hours off from the one its host meant,
    and nothing ever tells them: the zone is asked for instead of guessed.
    """
    response = await api.post(
        "/api/events",
        json={"title": "Supper", "starts_at": "2030-01-01T18:00:00"},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "zone" in response.json()["detail"]


@pytest.mark.parametrize(
    "header", [None, {}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-uuid"}]
)
async def test_planning_needs_someone_to_plan_as(api: AsyncClient, header: dict | None) -> None:
    response = await api.post(
        "/api/events", json={"title": "Book swap", "starts_at": at(1)}, headers=header or {}
    )
    assert response.status_code == 401


async def test_an_event_with_no_title_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/events", json={"title": "   ", "starts_at": at(1)}, headers=as_()
    )

    assert response.status_code == 400
    assert "needs a title" in response.json()["detail"]


async def test_an_event_named_over_what_a_card_holds_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/events", json={"title": "a" * 201, "starts_at": at(1)}, headers=as_()
    )

    assert response.status_code == 400
    assert "200" in response.json()["detail"]


async def test_an_event_named_exactly_what_a_card_holds_is_taken(api: AsyncClient) -> None:
    assert len((await plan(api, "a" * 200, starts_at=at(1)))["title"]) == 200


async def test_a_description_over_what_anyone_will_read_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(1), "details": "a" * 2001},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "2000" in response.json()["detail"]


@pytest.mark.parametrize(
    "starts_at, code",
    [(None, 422), (4, 422), ([], 422), ("next Tuesday", 400), ("2030-13-01", 400)],
)
async def test_an_event_with_no_readable_when_is_refused(
    api: AsyncClient, starts_at: object, code: int
) -> None:
    """A time nobody can place is the client's mistake.

    A field of the wrong shape is pydantic's refusal to read the body at all, and a
    string that is not a time gets Relay's sentence about it instead of a field-error
    shape of its own. Each input has one answer, and the test holds it to that one.
    """
    response = await api.post(
        "/api/events", json={"title": "Book swap", "starts_at": starts_at}, headers=as_()
    )

    assert response.status_code == code
    if code == 400:
        assert "not a time" in response.json()["detail"]


@pytest.mark.parametrize("title", [None, 4, []])
async def test_a_title_that_is_not_text_at_all_is_refused(api: AsyncClient, title: object) -> None:
    """A body that sends a title of the wrong shape never reaches the event at all."""
    response = await api.post(
        "/api/events", json={"title": title, "starts_at": at(1)}, headers=as_()
    )

    assert response.status_code == 422


async def test_an_event_that_ends_before_it_starts_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(10), "ends_at": at(9)},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "end" in response.json()["detail"]


async def test_an_event_that_ends_the_instant_it_starts_is_refused(api: AsyncClient) -> None:
    """An event that is over as it begins has not been planned, it has been mistyped."""
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(10), "ends_at": at(10)},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "end" in response.json()["detail"]


async def test_an_end_cleared_rather_than_omitted_is_no_end(api: AsyncClient) -> None:
    """`ends_at` emptied in a form is the host not knowing when it finishes, not a time."""
    event = await plan(api, "Book swap", starts_at=at(1), ends_at="   ")

    assert event["ends_at"] is None


async def test_a_venue_named_over_what_a_card_holds_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(1), "venue_name": "a" * 201},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "200" in response.json()["detail"]


async def test_a_place_and_a_description_of_nothing_at_all_are_kept_as_nothing(
    api: AsyncClient,
) -> None:
    """Blanks are stored as blanks, so a card never has to know that spaces mean empty."""
    event = await plan(api, "Book swap", starts_at=at(1), venue_name="   ", details=" \n ")

    assert (event["venue_name"], event["details"]) == (None, None)


@pytest.mark.parametrize("cell", ["not-a-cell", "a" * 40])
async def test_an_event_filed_where_no_locality_looks_is_refused(
    api: AsyncClient, cell: str
) -> None:
    """A 201 for an event nobody will ever list is a worse answer than a refusal."""
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(1), "location_cell": cell},
        headers=as_(),
    )

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


async def test_an_event_filed_at_the_wrong_resolution_is_refused(api: AsyncClient) -> None:
    """A res-9 cell matches no listing, so it is refused rather than quietly stored."""
    a_child_of_vigo = h3.cell_to_children(VIGO)[0]
    response = await api.post(
        "/api/events",
        json={"title": "Book swap", "starts_at": at(1), "location_cell": a_child_of_vigo},
        headers=as_(),
    )

    assert response.status_code == 400


async def test_a_locality_written_in_uppercase_lands_where_the_list_reads_it(
    api: AsyncClient,
) -> None:
    """One form on the way in, or the event is filed somewhere no read ever asks about."""
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO.upper())

    assert event["location_cell"] == VIGO
    assert [event["title"] for event in (await on(api))["events"]] == ["Book swap"]


async def test_a_locality_said_as_nothing_at_all_is_no_locality(api: AsyncClient) -> None:
    """An empty cell is the same as not saying where: kept, and in no locality's list."""
    event = await plan(api, "Somewhere, maybe", starts_at=at(1), location_cell="   ")

    assert event["location_cell"] is None
    assert (await on(api))["events"] == []


# Reading what is on.


async def test_the_list_of_what_is_on_is_public(api: AsyncClient) -> None:
    assert (await api.get("/api/events", params={"cell": VIGO})).status_code == 200


async def test_the_next_event_is_first_and_the_one_that_started_is_gone(api: AsyncClient) -> None:
    await plan(api, "tomorrow", starts_at=at(24), location_cell=VIGO)
    await plan(api, "tonight", starts_at=at(2), location_cell=VIGO)
    await plan(api, "already underway", starts_at=at(-1), location_cell=VIGO)
    await plan(api, "in another city", starts_at=at(3), location_cell=A_CORUNA)

    assert [event["title"] for event in (await on(api))["events"]] == ["tonight", "tomorrow"]


async def test_an_event_planned_without_a_place_is_in_no_localitys_list(api: AsyncClient) -> None:
    await plan(api, "nowhere in particular", starts_at=at(1))

    assert (await on(api))["events"] == []


async def test_a_narrower_radius_reads_fewer_events(api: AsyncClient) -> None:
    """The radius is the filter, so asking for less of the map has to change the answer."""
    lat, lng = h3.cell_to_latlng(VIGO)
    a_few_km_out = h3.latlng_to_cell(lat + 0.05, lng, 8)
    await plan(api, "next door", starts_at=at(1), location_cell=VIGO)
    await plan(api, "a few km out", starts_at=at(2), location_cell=a_few_km_out)

    wide = await on(api)
    narrow = (await api.get("/api/events", params={"cell": VIGO, "radius": 1})).json()

    assert [event["title"] for event in wide["events"]] == ["next door", "a few km out"]
    assert [event["title"] for event in narrow["events"]] == ["next door"]


async def test_the_widest_radius_the_list_will_read_is_read(api: AsyncClient) -> None:
    """25 km is the ceiling and it is inclusive, so it is answered, not refused."""
    await plan(api, "Down the road", starts_at=at(1), location_cell=VIGO)

    response = await api.get("/api/events", params={"cell": VIGO, "radius": 25})

    assert [event["title"] for event in response.json()["events"]] == ["Down the road"]


async def test_every_event_carries_how_many_are_going(api: AsyncClient) -> None:
    booked = await plan(api, "Book club", starts_at=at(1), location_cell=VIGO)
    await plan(api, "Silent reading", starts_at=at(2), location_cell=VIGO)
    await api.post(f"/api/events/{booked['id']}/rsvp", headers=as_(uuid4()))

    assert [(event["title"], event["rsvp_count"]) for event in (await on(api))["events"]] == [
        ("Book club", 1),
        ("Silent reading", 0),
    ]


async def test_the_list_pages_and_tells_you_where_the_next_page_starts(api: AsyncClient) -> None:
    for index in range(25):
        await plan(api, f"event {index}", starts_at=at(index + 1), location_cell=VIGO)

    first = (await api.get("/api/events", params={"cell": VIGO})).json()
    assert len(first["events"]) == 20
    assert first["next_from"] is not None
    # A `+` in a query string arrives as a space, which is no longer a timestamp.
    assert "+" not in first["next_from"]

    second = (
        await api.get("/api/events", params={"cell": VIGO, "from": first["next_from"]})
    ).json()

    assert [event["title"] for event in second["events"]] == [f"event {n}" for n in range(20, 25)]
    assert second["next_from"] is None
    seen = [event["id"] for event in first["events"] + second["events"]]
    assert len(set(seen)) == 25


async def test_events_that_all_start_at_the_same_time_still_page(api: AsyncClient) -> None:
    """A town's events all start at seven, and twenty of them will not fit on a page.

    A marker that named only the instant would resume past all twenty and the ones that
    did not fit would never be on any page: this is the bug a client would hit first.
    """
    seven = at(7)
    for index in range(25):
        await plan(api, f"choir {index}", starts_at=seven, location_cell=VIGO)

    first = (await api.get("/api/events", params={"cell": VIGO})).json()
    second = (
        await api.get("/api/events", params={"cell": VIGO, "from": first["next_from"]})
    ).json()

    assert len(first["events"]) == 20
    # The marker names the row the page stopped on, and nothing else could have.
    wall, _, row = first["next_from"].partition("~")
    assert datetime.fromisoformat(wall) == datetime.fromisoformat(first["events"][-1]["starts_at"])
    assert row == first["events"][-1]["id"]
    seen = [event["id"] for event in first["events"] + second["events"]]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert second["next_from"] is None


async def test_exactly_one_page_of_events_promises_no_second_one(api: AsyncClient) -> None:
    """`next_from` is a promise that there is more, and twenty with no twenty-first
    behind it is a full page with nothing to go on."""
    for index in range(20):
        await plan(api, f"event {index}", starts_at=at(index + 1), location_cell=VIGO)

    page = await on(api)

    assert len(page["events"]) == 20
    assert page["next_from"] is None


async def test_a_page_asked_for_from_another_zone_starts_at_the_same_instant(
    api: AsyncClient,
) -> None:
    """`from` is an instant, not a reading of one wall clock.

    The event at that instant is on the page, whichever zone the wall was written in.
    """
    for index in range(3):
        await plan(api, f"event {index}", starts_at=at(index + 1), location_cell=VIGO)

    in_tokyo = (NOW + timedelta(hours=2)).astimezone(TOKYO).isoformat()
    response = await api.get("/api/events", params={"cell": VIGO, "from": in_tokyo})

    assert [event["title"] for event in response.json()["events"]] == ["event 1", "event 2"]


async def test_a_date_without_a_time_reads_that_day(api: AsyncClient) -> None:
    """Someone typing `2030-05-11` means the day, so the day starts at its midnight."""
    await plan(api, "the night before", starts_at="2030-05-10T23:00:00Z", location_cell=VIGO)
    await plan(api, "the morning of", starts_at="2030-05-11T00:30:00Z", location_cell=VIGO)

    response = await api.get("/api/events", params={"cell": VIGO, "from": "2030-05-11"})

    assert [event["title"] for event in response.json()["events"]] == ["the morning of"]


async def test_the_list_needs_a_cell(api: AsyncClient) -> None:
    assert (await api.get("/api/events")).status_code == 422


@pytest.mark.parametrize("cell", ["", "not-a-cell"])
async def test_the_list_refuses_a_cell_it_cannot_read(api: AsyncClient, cell: str) -> None:
    response = await api.get("/api/events", params={"cell": cell})

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


@pytest.mark.parametrize("radius", [0, -1, 25.1, 26, float("nan"), float("inf")])
async def test_the_list_refuses_a_radius_that_would_read_too_far(
    api: AsyncClient, radius: float
) -> None:
    """A radius that reads the whole planet, or no distance at all, is the client's
    mistake to hear about rather than a query that hangs the request."""
    assert (
        await api.get("/api/events", params={"cell": VIGO, "radius": radius})
    ).status_code == 400


@pytest.mark.parametrize(
    "from_",
    [
        "yesterday",
        "2030-13-01",
        "1700000000",
        "9999-12-31T23:59:59-01:00",
        "2030-05-11T00:30:00Z~not-a-row",
        "~",
        "past~",
        "2030-05-11T00:30:00Z~abc~extra",
    ],
)
async def test_a_start_this_list_never_handed_out_is_refused(api: AsyncClient, from_: str) -> None:
    """A client that clears its marker may still send the parameter, and that is not a date.

    The last three are shaped like a marker this list hands out and were not: a made-up row
    is as unusable as a made-up day, and so is a half of one. `from` is one grammar, and a
    page request that does not fit it is a 400 rather than a silent reading of something
    else.
    """
    response = await api.get("/api/events", params={"cell": VIGO, "from": from_})

    assert response.status_code == 400


async def test_a_start_cleared_rather_than_omitted_reads_the_default_page(
    api: AsyncClient,
) -> None:
    """`from=` is a form field emptied, not a date: it means start from now like no marker."""
    await plan(api, "tomorrow", starts_at=at(24), location_cell=VIGO)

    cleared = await api.get("/api/events", params={"cell": VIGO, "from": ""})

    assert [event["title"] for event in cleared.json()["events"]] == ["tomorrow"]


async def test_a_start_that_arrived_with_a_space_where_the_plus_was(api: AsyncClient) -> None:
    """A `+` sent unencoded lands as a space, and that is not a time.

    The reason the marker this list hands out is written with a `Z` and never an offset.
    """
    response = await api.get(
        "/api/events", params={"cell": VIGO, "from": "2030-01-01T19:00:00 01:00"}
    )

    assert response.status_code == 400


async def test_an_event_starting_exactly_at_a_written_start_is_on_the_page(
    api: AsyncClient,
) -> None:
    """A time somebody writes down is where the reading picks up, and that row is on it.

    A date typed by a person means the day, and the supper that starts at midnight on it
    belongs to that day. A marker is the other thing: it names a row already read, and cuts
    strictly past itself — see the pages that walk past twenty events at one start time.
    """
    tonight = (await plan(api, "tonight", starts_at=at(6), location_cell=VIGO))["starts_at"]
    await plan(api, "later", starts_at=at(7), location_cell=VIGO)

    page = await api.get("/api/events", params={"cell": VIGO, "from": tonight})

    assert [event["title"] for event in page.json()["events"]] == ["tonight", "later"]


async def test_the_events_that_already_happened_are_behind_a_word_for_them(
    api: AsyncClient,
) -> None:
    """The default page is what has not started; `from=past` is how you ask for the rest.

    The rest means what already started: tomorrow is on the other side of now and stays
    on the forwards page, and the past reads back with the most recent first.
    """
    await plan(api, "last week", starts_at=at(-24 * 7), location_cell=VIGO)
    await plan(api, "tomorrow", starts_at=at(24), location_cell=VIGO)

    assert [event["title"] for event in (await on(api))["events"]] == ["tomorrow"]

    past = await api.get("/api/events", params={"cell": VIGO, "from": "past"})

    assert [event["title"] for event in past.json()["events"]] == ["last week"]


# Reading one event.


async def test_an_event_can_be_read_on_its_own(api: AsyncClient) -> None:
    created = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    response = await api.get(f"/api/events/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created | {"user_rsvped": False}


async def test_reading_an_event_says_whether_you_are_in_that_number(api: AsyncClient) -> None:
    """The count is for everyone; whose hand is in it is only ever said to the one asking."""
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    going = uuid4()
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_(going))

    assert (await api.get(f"/api/events/{event['id']}", headers=as_(going))).json()[
        "user_rsvped"
    ] is True
    assert (await api.get(f"/api/events/{event['id']}", headers=as_(uuid4()))).json()[
        "user_rsvped"
    ] is False


@pytest.mark.parametrize("header", [None, {}, {"Authorization": "Bearer not-a-uuid"}])
async def test_reading_an_event_without_a_token_to_read_it_as(
    api: AsyncClient, header: dict | None
) -> None:
    """The event is public, and a token that cannot be read is no reason to refuse it.

    `user_rsvped` answers a question about the reader, and a reader nobody could place
    has no answer: false, the same as the person who sent no token at all.
    """
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    unreadable = (await api.get(f"/api/events/{event['id']}", headers=header)).json()

    assert unreadable["rsvp_count"] == 1
    assert unreadable["user_rsvped"] is False


async def test_an_event_that_was_never_planned_is_not_there(api: AsyncClient) -> None:
    assert (await api.get(f"/api/events/{uuid4()}")).status_code == 404


async def test_an_id_that_is_not_an_id_is_not_an_event(api: AsyncClient) -> None:
    assert (await api.get("/api/events/not-a-uuid")).status_code == 422


# Saying you are going.


async def test_saying_you_are_going_counts_you(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    response = await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert response.status_code == 200
    assert response.json() == {"event_id": event["id"], "rsvp_count": 1}


async def test_saying_it_twice_is_refused_and_takes_no_second_place(api: AsyncClient) -> None:
    """One place per person, so the second tap is a conflict, not a silent second row."""
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    again = await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert again.status_code == 409
    assert "already" in again.json()["detail"]
    assert (await api.get(f"/api/events/{event['id']}")).json()["rsvp_count"] == 1


async def test_two_people_going_are_two_people_going(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_(uuid4()))
    last = await api.post(f"/api/events/{event['id']}/rsvp", headers=as_(uuid4()))

    assert last.json()["rsvp_count"] == 2
    assert (await api.get(f"/api/events/{event['id']}")).json()["rsvp_count"] == 2


async def test_a_place_can_be_taken_at_an_event_that_already_happened(api: AsyncClient) -> None:
    """Yesterday's session can still be marked as gone to.

    The listing is what hides a finished event, not a rule about who is allowed to say
    they were there: a host who forgot to tick their own supper last week still can.
    """
    event = await plan(api, "yesterday", starts_at=at(-24), location_cell=VIGO)

    going = await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert going.status_code == 200


async def test_the_host_who_says_they_are_going_is_in_the_number(api: AsyncClient) -> None:
    """Nothing says the one who planned it is not coming: the number counts everyone who
    said it, the host included."""
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    going = await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert going.json()["rsvp_count"] == 1
    assert (await api.get(f"/api/events/{event['id']}", headers=as_())).json()[
        "user_rsvped"
    ] is True


@pytest.mark.parametrize(
    "header", [None, {}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-uuid"}]
)
async def test_saying_you_are_going_needs_someone_to_say_it_as(
    api: AsyncClient, header: dict | None
) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    response = await api.post(f"/api/events/{event['id']}/rsvp", headers=header or {})

    assert response.status_code == 401


async def test_you_cannot_go_to_an_event_that_was_never_planned(api: AsyncClient) -> None:
    assert (await api.post(f"/api/events/{uuid4()}/rsvp", headers=as_())).status_code == 404


# Giving the place back.


async def test_giving_your_place_back_takes_you_out_of_the_number(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    response = await api.delete(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert response.status_code == 204
    assert response.text == ""
    assert (await api.get(f"/api/events/{event['id']}")).json()["rsvp_count"] == 0


async def test_giving_your_place_back_leaves_everyone_else_going(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    you = uuid4()
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_(you))
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())

    await api.delete(f"/api/events/{event['id']}/rsvp", headers=as_(you))

    assert (await api.get(f"/api/events/{event['id']}")).json()["rsvp_count"] == 1


async def test_giving_back_a_place_you_never_took_is_not_there(api: AsyncClient) -> None:
    """Nothing to give back is the same answer whichever way there was nothing: no event."""
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    assert (
        await api.delete(f"/api/events/{event['id']}/rsvp", headers=as_(uuid4()))
    ).status_code == 404


async def test_giving_back_a_place_twice_undoes_it_once(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)
    await api.post(f"/api/events/{event['id']}/rsvp", headers=as_())
    await api.delete(f"/api/events/{event['id']}/rsvp", headers=as_())

    assert (await api.delete(f"/api/events/{event['id']}/rsvp", headers=as_())).status_code == 404


async def test_giving_a_place_back_needs_someone_to_give_it_as(api: AsyncClient) -> None:
    event = await plan(api, "Book swap", starts_at=at(1), location_cell=VIGO)

    assert (await api.delete(f"/api/events/{event['id']}/rsvp", headers={})).status_code == 401


async def test_every_endpoint_is_in_the_openapi_document(api: AsyncClient) -> None:
    paths = (await api.get("/openapi.json")).json()["paths"]

    assert {"/api/events", "/api/events/{event_id}", "/api/events/{event_id}/rsvp"} <= set(paths)
