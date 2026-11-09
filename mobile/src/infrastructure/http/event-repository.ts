import type { AxiosInstance } from 'axios'

import { err, ok, type Event, type EventDetail, type EventError, type EventPage, type EventRepository } from '../../domain'
import { toApiError, statusOf } from './api-error'
import { EVENTS_PATH, eventPath, eventRsvpPath } from './endpoints'

export type EventDto = {
  id: string
  host_id: string
  host_name: string
  title: string
  starts_at: string
  ends_at?: string | null
  venue_name?: string | null
  details?: string | null
  location_cell?: string | null
  rsvp_count?: number
  /** Only `GET /events/:id` answers this, and only when it was given a token. */
  user_rsvped?: boolean
}

export const toEvent = (dto: EventDto): Event => ({
  id: dto.id,
  hostId: dto.host_id,
  hostName: dto.host_name,
  title: dto.title,
  startsAt: dto.starts_at,
  endsAt: dto.ends_at ?? null,
  venueName: dto.venue_name ?? null,
  details: dto.details ?? null,
  locationCell: dto.location_cell ?? null,
  rsvpCount: dto.rsvp_count ?? 0,
})

const toEventDetail = (dto: EventDto): EventDetail => ({ ...toEvent(dto), userRsvped: dto.user_rsvped ?? false })

/** A 404 means different things by verb, so the caller says which one it was. */
const toEventError = (error: unknown, notFound: EventError): EventError => {
  const status = statusOf(error)
  if (status === 401 || status === 403) return 'unauthorized'
  if (status === 404) return notFound
  if (status === 409) return 'already-going'
  return toApiError(error)
}

export const makeHttpEventRepository = ({ http }: { http: AxiosInstance }): EventRepository => ({
  async list({ cell, radiusKm, from }) {
    try {
      // `cell` is required by the server; `from` is a date, an instant, 'past', or the last next_from.
      const { data } = await http.get<{ events: EventDto[]; next_from?: string | null }>(EVENTS_PATH, {
        params: { cell, radius: radiusKm, ...(from ? { from } : {}) },
      })
      return ok<EventPage<Event>>({ events: (data.events ?? []).map(toEvent), nextFrom: data.next_from ?? null })
    } catch (error) {
      return err(toApiError(error))
    }
  },

  async get(id) {
    try {
      const { data } = await http.get<EventDto>(eventPath(id))
      return ok(toEventDetail(data))
    } catch (error) {
      return err(toEventError(error, 'not-found'))
    }
  },

  async create(event) {
    try {
      // starts_at has to carry a zone, and location_cell has to be a real resolution-8 cell.
      const { data } = await http.post<EventDto>(EVENTS_PATH, event)
      return ok(toEvent(data))
    } catch (error) {
      return err(toEventError(error, 'unexpected'))
    }
  },

  async rsvp(id) {
    try {
      const { data } = await http.post<{ rsvp_count?: number }>(eventRsvpPath(id))
      return ok(data.rsvp_count ?? 0)
    } catch (error) {
      return err(toEventError(error, 'not-found'))
    }
  },

  async cancelRsvp(id) {
    try {
      await http.delete(eventRsvpPath(id))
      return ok(undefined)
    } catch (error) {
      // Nothing to take back is its own answer, not a broken event.
      return err(toEventError(error, 'not-going'))
    }
  },
})
