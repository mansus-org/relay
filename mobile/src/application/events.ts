import {
  EVENTS_RADIUS_KM,
  err,
  ok,
  placeEvent,
  type ApiError,
  type CellEncoder,
  type EventDetail,
  type EventError,
  type EventRepository,
  type LatLng,
  type NearbyEvent,
  type NearbyEvents,
  type NewEvent,
  type Result,
} from '../domain'

type Deps = { readonly eventRepository: EventRepository; readonly cellEncoder: CellEncoder }

/** An event read from a cell, with the point it sits at and how far it is. */
export type DetailedEvent = EventDetail & { readonly distanceKm: number | null; readonly at: LatLng | null }

/**
 * One page of what is on nearby, plus the point the read was taken from — the map needs that middle
 * as much as the list needs the distances. `from` is the previous page's `next_from` when paging.
 */
export const makeLoadNearbyEvents =
  ({ eventRepository, cellEncoder }: Deps) =>
  async ({ cell, radiusKm = EVENTS_RADIUS_KM, from }: { cell: string; radiusKm?: number; from?: string }): Promise<Result<NearbyEvents, ApiError>> => {
    const page = await eventRepository.list({ cell, radiusKm, from })
    if (!page.ok) return err(page.error)
    const center = cellEncoder.centerOf(cell)
    return ok({
      center,
      nextFrom: page.value.nextFrom,
      events: page.value.events.map((event) => placeEvent(event, cellEncoder, center)),
    })
  }

/**
 * One event. The reader's cell is optional: without it there is nothing to measure the distance
 * against, and the screen says how far it is not, rather than guessing.
 */
export const makeLoadEvent =
  ({ eventRepository, cellEncoder }: Deps) =>
  async ({ id, cell }: { id: string; cell?: string | null }): Promise<Result<DetailedEvent, EventError>> => {
    const event = await eventRepository.get(id)
    if (!event.ok) return err(event.error)
    const from = cell ? cellEncoder.centerOf(cell) : null
    return ok(placeEvent(event.value, cellEncoder, from))
  }

/** Going to an event. Answers the new head count, which is the only number the list has to show. */
export const makeRsvpToEvent =
  ({ eventRepository }: Deps) =>
  async ({ eventId }: { eventId: string }): Promise<Result<number, EventError>> => eventRepository.rsvp(eventId)

/** Taking back an RSVP. The server answers with nothing, so the count is the client's to recount. */
export const makeCancelRsvp =
  ({ eventRepository }: Deps) =>
  async ({ eventId }: { eventId: string }): Promise<Result<void, EventError>> => eventRepository.cancelRsvp(eventId)

/** Putting an event on the map. The cell is the host's own; the server refuses one that is not real. */
export const makeCreateEvent =
  ({ eventRepository, cellEncoder }: Deps) =>
  async (event: NewEvent): Promise<Result<NearbyEvent, EventError>> => {
    const created = await eventRepository.create(event)
    if (!created.ok) return err(created.error)
    return ok(placeEvent(created.value, cellEncoder, null))
  }
