import { makeFakeCellEncoder } from '../../testing/fakes'
import {
  clusterEvents,
  draftToPayload,
  eventDayLabel,
  eventErrorMessage,
  eventsListMessage,
  formatEventDate,
  formatEventTime,
  groupEvents,
  MAX_EVENT_DETAILS_LENGTH,
  placeEvent,
  regionDeltaFor,
  todayParam,
  validateEventDraft,
  type Event,
  type EventDraft,
  type NearbyEvent,
} from '../event'

/** A fixed Wednesday at noon, so a test about days cannot drift. */
const now = new Date(2026, 10, 25, 12, 0, 0)
const inDays = (days: number, hour = 19) => {
  const date = new Date(now)
  date.setDate(date.getDate() + days)
  date.setHours(hour, 30, 0, 0)
  return date.toISOString()
}

const PORTO = { lat: 41.15, lng: -8.61 }
const LISBON = { lat: 38.72, lng: -9.14 }

const makeEvent = (id: string, over: Partial<Event> = {}): Event => ({
  id,
  hostId: 'u-1',
  hostName: 'Ana',
  title: 'Sunday market',
  startsAt: inDays(0),
  endsAt: null,
  venueName: null,
  details: null,
  locationCell: 'cell:41.15,-8.61',
  rsvpCount: 3,
  ...over,
})

const nearby = (id: string, at: NearbyEvent['at'], over: Partial<Event> = {}): NearbyEvent => ({
  ...makeEvent(id, over),
  at,
  distanceKm: at ? 2 : null,
})

describe('placeEvent', () => {
  const encoder = makeFakeCellEncoder()

  it('measures an event against where the reader asked from', () => {
    const placed = placeEvent(makeEvent('a'), encoder, PORTO)

    expect(placed.at).toEqual(PORTO)
    expect(placed.distanceKm).toBeCloseTo(0, 6)
  })

  it('leaves an event with no place off the map', () => {
    const placed = placeEvent(makeEvent('a', { locationCell: null }), encoder, PORTO)

    expect(placed.at).toBeNull()
    expect(placed.distanceKm).toBeNull()
  })

  it('will not invent a distance when the reader is nowhere', () => {
    expect(placeEvent(makeEvent('a'), encoder, null).distanceKm).toBeNull()
  })
})

describe('groupEvents', () => {
  it('buckets by how far off an event is, under the four names the ticket asks for', () => {
    const groups = groupEvents(
      [nearby('a', PORTO, { startsAt: inDays(0) }), nearby('b', PORTO, { startsAt: inDays(1) }), nearby('c', PORTO, { startsAt: inDays(4) }), nearby('d', PORTO, { startsAt: inDays(30) })],
      now,
    )

    expect(groups.map((group) => group.label)).toEqual(['Today', 'Tomorrow', 'This week', 'Later'])
  })

  it('leaves a section out when nothing falls in it', () => {
    const groups = groupEvents([nearby('a', PORTO, { startsAt: inDays(0) })], now)

    expect(groups).toHaveLength(1)
    expect(groups[0]?.key).toBe('today')
  })

  it('prints the date of the first event of a section, so a heading is never vague', () => {
    const groups = groupEvents([nearby('a', PORTO, { startsAt: inDays(4) })], now)

    expect(groups[0]?.dateLabel).toBe(formatEventDate(inDays(4)))
  })

  it('keeps the order the server sent inside a section', () => {
    const groups = groupEvents([nearby('late', PORTO, { startsAt: inDays(0, 22) }), nearby('early', PORTO, { startsAt: inDays(0, 9) })], now)

    expect(groups[0]?.events.map((event) => event.id)).toEqual(['late', 'early'])
  })

  it('has nothing to say about an empty list', () => {
    expect(groupEvents([], now)).toEqual([])
  })
})

describe('clusterEvents', () => {
  it('merges events standing within a few streets into one pin', () => {
    const beside = { lat: 41.1512, lng: -8.6109 }
    const pins = clusterEvents([nearby('a', PORTO), nearby('b', beside)])

    expect(pins).toHaveLength(1)
    expect(pins[0]?.events.map((event) => event.id)).toEqual(['a', 'b'])
  })

  it('keeps a pin per event once they are in different parts of the city', () => {
    const pins = clusterEvents([nearby('a', PORTO), nearby('b', LISBON)])

    expect(pins).toHaveLength(2)
  })

  it('puts the pin in the middle of what it holds', () => {
    const [pin] = clusterEvents([nearby('a', PORTO), nearby('b', LISBON)], 400)

    expect(pin?.at.lat).toBeCloseTo((PORTO.lat + LISBON.lat) / 2, 6)
  })

  it('cannot put on the map what has no place', () => {
    expect(clusterEvents([nearby('a', null)])).toEqual([])
  })
})

describe('validateEventDraft', () => {
  const draft: EventDraft = { title: 'Sunday market', startsAt: new Date(2026, 10, 26, 19, 0), endsAt: null, venueName: '', details: '', locationCell: 'cell:41.15,-8.61' }

  it('wants a name and a start', () => {
    expect(validateEventDraft({ ...draft, title: '   ' }).title).toBeTruthy()
    expect(validateEventDraft({ ...draft, startsAt: null }).startsAt).toBeTruthy()
  })

  it('will not accept an end that comes before the start', () => {
    expect(validateEventDraft({ ...draft, endsAt: new Date(2026, 10, 26, 18, 0) }).endsAt).toBeTruthy()
  })

  it('stops the details before the server does', () => {
    expect(validateEventDraft({ ...draft, details: 'x'.repeat(MAX_EVENT_DETAILS_LENGTH + 1) }).details).toBeTruthy()
  })

  it('lets a plain evening through untouched', () => {
    expect(validateEventDraft(draft)).toEqual({})
  })
})

describe('draftToPayload', () => {
  const draft: EventDraft = { title: '  Sunday market ', startsAt: new Date(2026, 10, 26, 19, 0), endsAt: null, venueName: '  ', details: '', locationCell: 'cell:41.15,-8.61' }

  it('sends only what the host actually filled in', () => {
    expect(draftToPayload(draft)).toEqual({ title: 'Sunday market', startsAt: expect.any(String), locationCell: 'cell:41.15,-8.61' })
  })

  it('sends an instant with a zone, which is what the server parses', () => {
    expect(draftToPayload(draft).startsAt).toMatch(/(Z|[+-]\d{2}:\d{2})$/)
  })

  it('keeps an end that comes after the start', () => {
    const payload = draftToPayload({ ...draft, endsAt: new Date(2026, 10, 26, 22, 0), venueName: ' The back room ' })

    expect(payload.endsAt).toBeTruthy()
    expect(payload.venueName).toBe('The back room')
  })
})

describe('todayParam', () => {
  it('is a date with no clock on it', () => {
    expect(todayParam(now)).toBe('2026-11-25')
  })
})

describe('eventErrorMessage', () => {
  it('says a second RSVP is not a second place', () => {
    expect(eventErrorMessage('already-going')).toMatch(/already/i)
  })

  it('says an event is gone rather than missing', () => {
    expect(eventErrorMessage('not-found')).toMatch(/gone/i)
  })

  it('asks for a sign in before it lets you RSVP', () => {
    expect(eventErrorMessage('unauthorized')).toMatch(/sign in/i)
  })

  it('does not blame the server for a dead network', () => {
    expect(eventErrorMessage('network')).toMatch(/connection/i)
  })

  it('names the list when the list is what failed', () => {
    expect(eventsListMessage('network')).toMatch(/Relay/i)
    expect(eventsListMessage('unexpected')).toMatch(/try again/i)
  })
})

describe('the clock on a row', () => {
  it('prints the hour in the reader’s own day', () => {
    expect(formatEventTime(inDays(0, 19))).toBe('19:30')
    expect(formatEventDate(now)).toBe('Wed, Nov 25')
  })

  it('names today, tomorrow, then the day', () => {
    expect(eventDayLabel(inDays(0), now)).toBe('Today')
    expect(eventDayLabel(inDays(1), now)).toBe('Tmrw')
    expect(eventDayLabel(inDays(3), now)).toBe('Sat')
  })

  it('takes a Date as readily as an instant from the server', () => {
    expect(formatEventTime(new Date(2026, 10, 25, 8, 5))).toBe('08:05')
  })

  it('says nothing when there is no time to print', () => {
    expect(formatEventTime('not an instant')).toBe('')
  })

  it('opens the map wide enough for the radius on both sides', () => {
    expect(regionDeltaFor(50)).toBeCloseTo(100 / 111, 6)
  })
})
