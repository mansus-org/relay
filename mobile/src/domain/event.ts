import { distanceInKm } from './community'
import type { ApiError, LatLng } from './post'
import type { CellEncoder } from './ports'

/** Events are read at the same reach as the feed. The server allows 0-25 km; we never ask for more. */
export const EVENTS_RADIUS_KM = 10

/** The server takes any string for these. The limits are ours, and the form counts against them. */
export const MAX_EVENT_TITLE_LENGTH = 200
export const MAX_EVENT_VENUE_LENGTH = 120
export const MAX_EVENT_DETAILS_LENGTH = 500

/** One event as the events API returns it. */
export type Event = {
  readonly id: string
  readonly hostId: string
  readonly hostName: string
  readonly title: string
  /** Zone-aware instant: the server refuses a naive one. */
  readonly startsAt: string
  readonly endsAt: string | null
  readonly venueName: string | null
  readonly details: string | null
  /** Resolution-8 cell of the meeting point. Null means the event cannot be put on a map. */
  readonly locationCell: string | null
  readonly rsvpCount: number
}

/** Only `GET /events/:id` answers whether you are going, and only when it got a token. */
export type EventDetail = Event & { readonly userRsvped: boolean }

/** A page of anything the events API pages: pass `nextFrom` back as `from` for the next one. */
export type EventPage<T> = { readonly events: readonly T[]; readonly nextFrom: string | null }

/** An event measured against the cell it was read from. */
export type NearbyEvent = Event & { readonly distanceKm: number | null; readonly at: LatLng | null }

/** One read of the events API: the page, plus the point it was read from (the map's middle). */
export type NearbyEvents = EventPage<NearbyEvent> & { readonly center: LatLng }

/** The body of `POST /events`. `startsAt` must carry a zone or the server answers 400. */
export type NewEvent = {
  title: string
  startsAt: string
  endsAt?: string
  venueName?: string
  details?: string
  locationCell?: string
}

/**
 * Every answer is a word now: 'already-going' is a second RSVP refused (409), not a second place.
 * The server's own text is not carried, the same way the communities repository drops it.
 */
export type EventError = ApiError | 'not-found' | 'unauthorized' | 'already-going' | 'not-going'

const EVENT_MESSAGES: Record<EventError, string> = {
  network: 'Could not reach Relay. Check your connection and try again.',
  unexpected: 'Something went wrong with that event.',
  'not-found': 'That event is gone.',
  unauthorized: 'Sign in to do that with an event.',
  'already-going': "You're already going.",
  'not-going': "You weren't going to that one.",
}

export const eventErrorMessage = (error: EventError): string => EVENT_MESSAGES[error]

/** Reading the list can only fail on transport, and "that event" would name nothing. */
export const eventsListMessage = (error: ApiError): string =>
  error === 'network' ? EVENT_MESSAGES.network : 'Relay could not read the events nearby. Try again in a moment.'

/** The event's own point on the map, or null when the host gave no place. */
export const placeEvent = <T extends Event>(
  event: T,
  cellEncoder: CellEncoder,
  from: LatLng | null,
): T & { readonly distanceKm: number | null; readonly at: LatLng | null } => {
  const at = event.locationCell ? cellEncoder.centerOf(event.locationCell) : null
  return { ...event, at, distanceKm: at && from ? distanceInKm(from, at) : null }
}

const DAY_MS = 86_400_000
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad = (n: number) => String(n).padStart(2, '0')
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate())

/** Whole calendar days from `from` to `to`; rounding absorbs the DST hour so a day is a day. */
const daysApart = (from: Date, to: Date) => Math.round((startOfDay(to).getTime() - startOfDay(from).getTime()) / DAY_MS)

/** "19:30". Relay is in Portuguese and Spanish, and the mockups are on the 24-hour clock. */
export const formatEventTime = (instant: string): string => {
  const date = new Date(instant)
  return Number.isNaN(date.getTime()) ? '' : `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** "Sat, Oct 25" — the day an event falls on, in the reader's own calendar. */
export const formatEventDate = (instant: string): string => {
  const date = new Date(instant)
  return Number.isNaN(date.getTime()) ? '' : `${DAYS[date.getDay()]}, ${MONTHS[date.getMonth()]} ${date.getDate()}`
}

/** The small line in a row's time block: the day, once you stop needing the word "today". */
export const eventDayLabel = (instant: string, now: Date): string => {
  const date = new Date(instant)
  if (Number.isNaN(date.getTime())) return ''
  const apart = daysApart(now, date)
  if (apart <= 0) return 'Today'
  if (apart === 1) return 'Tmrw'
  return apart < 7 ? DAYS[date.getDay()] : `${MONTHS[date.getMonth()]} ${date.getDate()}`
}

/**
 * The `from` value that opens the list: today at midnight, so an event that started an hour ago is
 * still in today's section instead of vanishing until tomorrow.
 */
export const todayParam = (now: Date): string =>
  `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

/** A section of the list. The four names are the ticket's; a section is only drawn when it has events. */
export type EventGroupKey = 'today' | 'tomorrow' | 'week' | 'later'
export type EventGroup = { readonly key: EventGroupKey; readonly label: string; readonly dateLabel: string; readonly events: readonly NearbyEvent[] }

const GROUP_LABELS: Record<EventGroupKey, string> = { today: 'Today', tomorrow: 'Tomorrow', week: 'This week', later: 'Later' }

const groupOf = (instant: string, now: Date): EventGroupKey => {
  const apart = daysApart(now, new Date(instant))
  if (apart <= 0) return 'today'
  if (apart === 1) return 'tomorrow'
  return apart < 7 ? 'week' : 'later'
}

/**
 * Group by how far off the event is, not by its calendar day: seven days out would otherwise print
 * seven headings to say "this week". Each section shows the date of its first event, and every row
 * carries its own day, so nothing is hidden by the coarser heading.
 */
export const groupEvents = (events: readonly NearbyEvent[], now: Date): readonly EventGroup[] => {
  const buckets = new Map<EventGroupKey, NearbyEvent[]>()
  for (const event of events) {
    const key = groupOf(event.startsAt, now)
    const bucket = buckets.get(key)
    if (bucket) bucket.push(event)
    else buckets.set(key, [event])
  }
  return (['today', 'tomorrow', 'week', 'later'] as const)
    .filter((key) => buckets.has(key))
    .map((key) => {
      const group = buckets.get(key) as NearbyEvent[]
      return { key, label: GROUP_LABELS[key], dateLabel: formatEventDate(group[0].startsAt), events: group }
    })
}

/** A pin on the map: one event, or several standing close enough to share a mark. */
export type MapPin = { readonly id: string; readonly at: LatLng; readonly events: readonly NearbyEvent[] }

/**
 * Events in one square of a city would otherwise stack pins nobody can tap. Anything within
 * `sizeKm` of a pin joins it, and the pin moves to the middle of what it holds. Order is the list's,
 * so the same page always draws the same pins.
 */
export const clusterEvents = (events: readonly NearbyEvent[], sizeKm = 3): readonly MapPin[] => {
  const pins: { id: string; at: LatLng; events: NearbyEvent[]; lat: number; lng: number }[] = []
  for (const event of events) {
    if (!event.at) continue
    const near = pins.find((pin) => distanceInKm(pin.at, event.at as LatLng) <= sizeKm)
    if (near) {
      near.events.push(event)
      near.lat += event.at.lat
      near.lng += event.at.lng
      near.at = { lat: near.lat / near.events.length, lng: near.lng / near.events.length }
    } else {
      pins.push({ id: event.id, at: event.at, events: [event], lat: event.at.lat, lng: event.at.lng })
    }
  }
  return pins.map(({ id, at, events: group }) => ({ id, at, events: group }))
}

/** How wide a map has to be to show `radiusKm` on either side of the reader. */
export const regionDeltaFor = (radiusKm: number): number => (radiusKm / 111) * 2

/** The form's own state, before any of it is a request body. */
export type EventDraft = {
  title: string
  startsAt: Date | null
  endsAt: Date | null
  venueName: string
  details: string
  locationCell: string | null
}

export type DraftErrors = { title?: string; startsAt?: string; endsAt?: string; details?: string }

/** What the form has to fix before it is worth posting, and in the app's words, not the server's. */
export const validateEventDraft = (draft: EventDraft): DraftErrors => {
  const errors: DraftErrors = {}
  const title = draft.title.trim()
  if (!title) errors.title = 'Give the event a name.'
  else if (title.length > MAX_EVENT_TITLE_LENGTH) errors.title = `Keep the name under ${MAX_EVENT_TITLE_LENGTH} characters.`
  if (!draft.startsAt) errors.startsAt = 'When does it start?'
  if (draft.startsAt && draft.endsAt && draft.endsAt.getTime() <= draft.startsAt.getTime()) {
    errors.endsAt = 'The end has to come after the start.'
  }
  if (draft.details.length > MAX_EVENT_DETAILS_LENGTH) errors.details = `Keep the details under ${MAX_EVENT_DETAILS_LENGTH} characters.`
  return errors
}

export const draftHasErrors = (errors: DraftErrors): boolean => Object.keys(errors).length > 0

/**
 * The request body. Times go out as UTC with its "Z", which is what makes them zone-aware enough
 * for the server; empty fields are left off rather than sent as blanks.
 */
export const draftToPayload = (draft: EventDraft): NewEvent => {
  const payload: NewEvent = { title: draft.title.trim(), startsAt: (draft.startsAt as Date).toISOString() }
  if (draft.endsAt && draft.endsAt.getTime() > draft.startsAt!.getTime()) payload.endsAt = draft.endsAt.toISOString()
  const venue = draft.venueName.trim()
  if (venue) payload.venueName = venue
  const details = draft.details.trim()
  if (details) payload.details = details
  if (draft.locationCell) payload.locationCell = draft.locationCell
  return payload
}
