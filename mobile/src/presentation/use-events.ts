import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState } from 'react-native'

import type { DetailedEvent } from '../application'
import {
  EVENTS_RADIUS_KM,
  createEventMessage,
  draftToPayload,
  eventErrorMessage,
  eventsListMessage,
  todayParam,
  validateEventDraft,
  type Community,
  type DraftErrors,
  type EventDraft,
  type LatLng,
  type NearbyEvent,
} from '../domain'
import { useUseCases } from './use-cases'

export type EventsPhase = 'locating' | 'denied' | 'ready'

export type EventsState = {
  phase: EventsPhase
  canAskAgain: boolean
  placeName: string | null
  /** The cell every read was taken from; the create form offers it back as the event's place. */
  cell: string | null
  center: LatLng | null
  events: readonly NearbyEvent[]
  /** Pass back as `from` for the next page; null once the server has run out. */
  nextFrom: string | null
  refreshing: boolean
  loadingMore: boolean
  failed: boolean
  /** Why the last read failed, in the app's words; null while it has not failed. */
  error: string | null
}

const initial: EventsState = {
  phase: 'locating',
  canAskAgain: true,
  placeName: null,
  cell: null,
  center: null,
  events: [],
  nextFrom: null,
  refreshing: false,
  loadingMore: false,
  failed: false,
  error: null,
}

/**
 * What is on within reach of wherever you are, from today forwards. The list and the map are the
 * same read: one page, one centre, two ways of drawing it.
 */
export function useEvents() {
  const { resolveLocation, loadNearbyEvents } = useUseCases()
  const [state, setState] = useState<EventsState>(initial)
  const patch = useCallback((next: Partial<EventsState>) => setState((s) => ({ ...s, ...next })), [])
  // Paging needs the cell the page came from, and it must be the one that is on screen right now.
  const cell = useRef<string | null>(null)

  const start = useCallback(
    async (prompt: boolean) => {
      const location = await resolveLocation({ prompt })
      if (!location.ok) {
        if (location.error.kind === 'denied') patch({ phase: 'denied', canAskAgain: location.error.canAskAgain, refreshing: false })
        else patch({ phase: 'ready', failed: true, error: eventsListMessage('unexpected'), refreshing: false })
        return
      }
      cell.current = location.value.cell
      const result = await loadNearbyEvents({ cell: location.value.cell, radiusKm: EVENTS_RADIUS_KM, from: todayParam(new Date()) })
      if (result.ok) {
        patch({
          phase: 'ready',
          placeName: location.value.placeName,
          cell: location.value.cell,
          center: result.value.center,
          events: result.value.events,
          nextFrom: result.value.nextFrom,
          failed: false,
          error: null,
          refreshing: false,
        })
      } else patch({ phase: 'ready', placeName: location.value.placeName, cell: location.value.cell, failed: true, error: eventsListMessage(result.error), refreshing: false })
    },
    [resolveLocation, loadNearbyEvents, patch],
  )

  useEffect(() => {
    // start() only reaches state after its first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start(true)
  }, [start])

  const denied = state.phase === 'denied'
  useEffect(() => {
    if (!denied) return
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') void start(false)
    })
    return () => sub.remove()
  }, [denied, start])

  const refresh = useCallback(async () => {
    patch({ refreshing: true })
    await start(false)
  }, [start, patch])

  /**
   * The next page, appended. `from` is the cursor the last page handed back, so paging walks the
   * timeline forward instead of guessing at offsets.
   */
  const loadMore = useCallback(async () => {
    const at = cell.current
    if (!at || !state.nextFrom || state.loadingMore) return
    patch({ loadingMore: true })
    const result = await loadNearbyEvents({ cell: at, radiusKm: EVENTS_RADIUS_KM, from: state.nextFrom })
    if (result.ok) {
      setState((s) => ({ ...s, events: [...s.events, ...result.value.events], nextFrom: result.value.nextFrom, loadingMore: false }))
    } else patch({ loadingMore: false })
  }, [state.nextFrom, state.loadingMore, loadNearbyEvents, patch])

  return { state, enableLocation: () => start(true), refresh, loadMore }
}

export type EventDetailState = {
  loaded: boolean
  failed: boolean
  event: DetailedEvent | null
  /** Yours until the server answers: the list cannot tell you, only the event can. */
  going: boolean
  count: number
  busy: boolean
  error: string | null
}

/** One event, and the two things you can do to it. */
export function useEventDetail(id: string) {
  const { resolveLocation, loadEvent, rsvpToEvent, cancelRsvp } = useUseCases()
  const [state, setState] = useState<EventDetailState>({ loaded: false, failed: false, event: null, going: false, count: 0, busy: false, error: null })

  useEffect(() => {
    let cancelled = false
    void (async () => {
      // No prompt here: you came from a list that already asked, and a distance is not worth a dialog.
      const location = await resolveLocation({ prompt: false })
      const result = await loadEvent({ id, cell: location.ok ? location.value.cell : null })
      if (cancelled) return
      if (result.ok) {
        setState({
          loaded: true,
          failed: false,
          event: result.value,
          going: result.value.userRsvped,
          count: result.value.rsvpCount,
          busy: false,
          error: null,
        })
      } else setState({ loaded: true, failed: true, event: null, going: false, count: 0, busy: false, error: eventErrorMessage(result.error) })
    })()
    return () => {
      cancelled = true
    }
  }, [id, resolveLocation, loadEvent])

  /**
   * Going, or not going. The count moves the moment you tap and moves back if the server refuses —
   * a second RSVP is a 409, and that is the one case where the number you guessed was never right.
   */
  const toggle = useCallback(async () => {
    if (!state.event || state.busy) return
    const next = !state.going
    const back = state.count
    setState((s) => ({ ...s, busy: true, error: null, going: next, count: back + (next ? 1 : -1) }))
    if (next) {
      const result = await rsvpToEvent({ eventId: id })
      if (result.ok) setState((s) => ({ ...s, busy: false, count: result.value }))
      else setState((s) => ({ ...s, busy: false, going: false, count: back, error: eventErrorMessage(result.error) }))
      return
    }
    const result = await cancelRsvp({ eventId: id })
    if (!result.ok) setState((s) => ({ ...s, busy: false, going: true, count: back, error: eventErrorMessage(result.error) }))
    else setState((s) => ({ ...s, busy: false }))
  }, [state.event, state.busy, state.going, state.count, id, rsvpToEvent, cancelRsvp])

  return { state, toggle }
}

const emptyDraft: EventDraft = { title: '', startsAt: null, endsAt: null, venueName: '', details: '', locationCell: null, communityId: null }

/** The first nudge on an empty form lands on an evening tomorrow, which is what most of these are. */
const defaultStart = (): Date => {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  date.setHours(19, 0, 0, 0)
  return date
}

export type EventDraftState = {
  draft: EventDraft
  errors: DraftErrors
  busy: boolean
  error: string | null
  /** The place the form defaulted to, so the screen can say where it put the event. */
  placeName: string | null
  /** The communities you belong to, and so can file an event under. Empty when you are in none. */
  communities: readonly Community[]
}

/** Making an event. The cell defaults to where you are standing; the server refuses a fake one. */
export function useCreateEvent() {
  const { resolveLocation, listJoinedCommunities, createEvent } = useUseCases()
  const [state, setState] = useState<EventDraftState>({ draft: emptyDraft, errors: {}, busy: false, error: null, placeName: null, communities: [] })

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const location = await resolveLocation({ prompt: false })
      if (cancelled || !location.ok) return
      setState((s) => ({ ...s, draft: { ...s.draft, locationCell: location.value.cell }, placeName: location.value.placeName }))
    })()
    void listJoinedCommunities().then((result) => {
      if (!cancelled && result.ok) setState((s) => ({ ...s, communities: result.value }))
    })
    return () => {
      cancelled = true
    }
  }, [resolveLocation, listJoinedCommunities])

  const set = useCallback((next: Partial<EventDraft>) => setState((s) => ({ ...s, draft: { ...s.draft, ...next }, errors: {} })), [])
  /** Filing it under one of yours, or un-filing it. Tapping the one that is on takes it back off. */
  const toggleCommunity = useCallback(
    (id: string) => setState((s) => ({ ...s, draft: { ...s.draft, communityId: s.draft.communityId === id ? null : id } })),
    [],
  )
  /** Steps the start, and the end along with it, so an evening does not get torn apart by one tap. */
  const shiftStart = useCallback(
    (ms: number) =>
      setState((s) => {
        const at = new Date((s.draft.startsAt ?? defaultStart()).getTime() + ms)
        const endsAt = s.draft.endsAt ? new Date(s.draft.endsAt.getTime() + ms) : null
        return { ...s, errors: {}, draft: { ...s.draft, startsAt: at, endsAt } }
      }),
    [],
  )

  /** Returns the new event's id, or null when the server said no. */
  const submit = useCallback(async (): Promise<string | null> => {
    const errors = validateEventDraft(state.draft)
    if (!state.draft.startsAt) errors.startsAt = errors.startsAt ?? 'When does it start?'
    if (Object.keys(errors).length > 0) {
      setState((s) => ({ ...s, errors }))
      return null
    }
    setState((s) => ({ ...s, busy: true, error: null }))
    const result = await createEvent(draftToPayload(state.draft))
    if (result.ok) {
      setState((s) => ({ ...s, busy: false }))
      return result.value.id
    }
    setState((s) => ({ ...s, busy: false, error: createEventMessage(result.error) }))
    return null
  }, [state.draft, createEvent])

  return { state, set, shiftStart, toggleCommunity, submit }
}
