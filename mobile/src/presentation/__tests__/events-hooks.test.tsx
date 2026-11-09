import { act, create } from 'react-test-renderer'

import type { UseCases } from '../../application'
import { err, ok, type Event, type EventDetail, type LatLng, type NearbyEvent } from '../../domain'
import { useCreateEvent, useEventDetail, useEvents } from '../use-events'
import { UseCasesProvider } from '../use-cases'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

function mount<T>(hook: () => T, overrides: Partial<UseCases>) {
  const result = { current: undefined as unknown as T }
  function Probe() {
    result.current = hook()
    return null
  }
  let renderer: ReturnType<typeof create>
  act(() => {
    renderer = create(
      <UseCasesProvider useCases={overrides as UseCases}>
        <Probe />
      </UseCasesProvider>,
    )
  })
  return { result, unmount: () => act(() => renderer.unmount()) }
}

const located = ok({ cell: 'cell-1', placeName: 'Pinheiros' })

const makeEvent = (id: string, over: Partial<Event> = {}): Event => ({
  id,
  hostId: 'u-1',
  hostName: 'Ana',
  title: `Event ${id}`,
  startsAt: '2026-11-25T19:30:00+00:00',
  endsAt: null,
  venueName: null,
  details: null,
  locationCell: 'cell-1',
  rsvpCount: 2,
  ...over,
})

const nearby = (id: string, over: Partial<Event> = {}): NearbyEvent => ({ ...makeEvent(id, over), at: { lat: -23.56, lng: -46.69 }, distanceKm: 1 })

const page = (ids: readonly string[], nextFrom: string | null = null) => ok({ center: { lat: -23.56, lng: -46.69 }, nextFrom, events: ids.map((id) => nearby(id)) })

/** One event as the detail endpoint answers it: not going, nowhere in particular, until a test says so. */
const detailed = (id: string, over: Partial<EventDetail> = {}) => ({ userRsvped: false, at: null as LatLng | null, distanceKm: null as number | null, ...makeEvent(id, over), ...over })

describe('useEvents', () => {
  it('reads today forwards from wherever the reader turned out to be', async () => {
    const loadNearbyEvents = jest.fn(async () => page(['a', 'b']))
    const resolveLocation = jest.fn(async () => located)
    const t = mount(useEvents, { resolveLocation, loadNearbyEvents } as unknown as Partial<UseCases>)
    await flush()

    expect(resolveLocation).toHaveBeenCalledWith({ prompt: true })
    expect(loadNearbyEvents).toHaveBeenCalledWith({ cell: 'cell-1', radiusKm: 10, from: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) })
    const { state } = t.result.current
    expect([state.phase, state.placeName, state.events.map((e) => e.id)]).toEqual(['ready', 'Pinheiros', ['a', 'b']])
    t.unmount()
  })

  it('asks before it takes a location, and says so when the answer is no', async () => {
    const loadNearbyEvents = jest.fn()
    const t = mount(useEvents, { resolveLocation: jest.fn(async () => err({ kind: 'denied' as const, canAskAgain: true })), loadNearbyEvents } as unknown as Partial<UseCases>)
    await flush()

    expect(t.result.current.state.phase).toBe('denied')
    expect(t.result.current.state.canAskAgain).toBe(true)
    expect(loadNearbyEvents).not.toHaveBeenCalled()
    t.unmount()
  })

  it('says what went wrong when the server would not answer', async () => {
    const t = mount(useEvents, { resolveLocation: jest.fn(async () => located), loadNearbyEvents: jest.fn(async () => err('network')) } as unknown as Partial<UseCases>)
    await flush()

    expect(t.result.current.state.failed).toBe(true)
    expect(t.result.current.state.error).toMatch(/connection/i)
    t.unmount()
  })

  it('pulls the next page onto what is already on screen, using the cursor it was handed', async () => {
    const loadNearbyEvents = jest
      .fn()
      .mockResolvedValueOnce(page(['a'], 'cursor'))
      .mockResolvedValueOnce(page(['b'], null))
    const t = mount(useEvents, { resolveLocation: jest.fn(async () => located), loadNearbyEvents } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.loadMore()))

    expect(loadNearbyEvents).toHaveBeenLastCalledWith({ cell: 'cell-1', radiusKm: 10, from: 'cursor' })
    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.nextFrom).toBeNull()
    t.unmount()
  })

  it('does not go looking for a page the server never offered', async () => {
    const loadNearbyEvents = jest.fn(async () => page(['a']))
    const t = mount(useEvents, { resolveLocation: jest.fn(async () => located), loadNearbyEvents } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.loadMore()))

    expect(loadNearbyEvents).toHaveBeenCalledTimes(1)
    t.unmount()
  })

  it('reads again from scratch when the reader pulls down', async () => {
    const loadNearbyEvents = jest.fn().mockResolvedValueOnce(page(['a'])).mockResolvedValueOnce(page(['c']))
    const t = mount(useEvents, { resolveLocation: jest.fn(async () => located), loadNearbyEvents } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.refresh()))

    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['c'])
    expect(t.result.current.state.refreshing).toBe(false)
    t.unmount()
  })
})

describe('useEventDetail', () => {
  it('measures the event against where the reader is, when the app is allowed to know', async () => {
    const loadEvent = jest.fn(async () => ok({ ...detailed('a', { userRsvped: true, rsvpCount: 7 }), at: { lat: 0, lng: 0 }, distanceKm: 2 }))
    const t = mount(() => useEventDetail('a'), { resolveLocation: jest.fn(async () => located), loadEvent } as unknown as Partial<UseCases>)
    await flush()

    expect(loadEvent).toHaveBeenCalledWith({ id: 'a', cell: 'cell-1' })
    expect(t.result.current.state).toMatchObject({ loaded: true, going: true, count: 7 })
    t.unmount()
  })

  it('still opens an event when the reader would not say where they are', async () => {
    const loadEvent = jest.fn(async () => ok(detailed('a')))
    const t = mount(() => useEventDetail('a'), { resolveLocation: jest.fn(async () => err({ kind: 'denied' as const, canAskAgain: false })), loadEvent } as unknown as Partial<UseCases>)
    await flush()

    expect(loadEvent).toHaveBeenCalledWith({ id: 'a', cell: null })
    expect(t.result.current.state.going).toBe(false)
    t.unmount()
  })

  it('says the event is gone in the reader’s words', async () => {
    const t = mount(() => useEventDetail('a'), { resolveLocation: jest.fn(async () => located), loadEvent: jest.fn(async () => err('not-found')) } as unknown as Partial<UseCases>)
    await flush()

    expect(t.result.current.state.error).toMatch(/gone/i)
    t.unmount()
  })

  it('moves the number the moment you tap, and keeps what the server counted', async () => {
    const rsvpToEvent = jest.fn(async () => ok(9))
    const t = mount(() => useEventDetail('a'), { resolveLocation: jest.fn(async () => located), loadEvent: jest.fn(async () => ok(detailed('a'))), rsvpToEvent } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.toggle()))

    expect(rsvpToEvent).toHaveBeenCalledWith({ eventId: 'a' })
    expect(t.result.current.state).toMatchObject({ going: true, count: 9, busy: false, error: null })
    t.unmount()
  })

  it('takes the number back when the server refused the place', async () => {
    const t = mount(() => useEventDetail('a'), {
      resolveLocation: jest.fn(async () => located),
      loadEvent: jest.fn(async () => ok(detailed('a'))),
      rsvpToEvent: jest.fn(async () => err('already-going')),
    } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.toggle()))

    expect(t.result.current.state).toMatchObject({ going: false, count: 2, error: "You're already going." })
    t.unmount()
  })

  it('takes the place back when you tap a second time', async () => {
    const cancelRsvp = jest.fn(async () => ok(undefined))
    const t = mount(() => useEventDetail('a'), {
      resolveLocation: jest.fn(async () => located),
      loadEvent: jest.fn(async () => ok(detailed('a', { userRsvped: true }))),
      cancelRsvp,
    } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.toggle()))

    expect(cancelRsvp).toHaveBeenCalledWith({ eventId: 'a' })
    expect(t.result.current.state).toMatchObject({ going: false, count: 1 })
    t.unmount()
  })
})

describe('useCreateEvent', () => {
  const filled = { title: 'Sunday market', startsAt: new Date(2026, 10, 26, 19, 0) }

  it('offers the place you are standing as the place of the event', async () => {
    const t = mount(useCreateEvent, { resolveLocation: jest.fn(async () => located) } as unknown as Partial<UseCases>)
    await flush()

    expect(t.result.current.state.draft.locationCell).toBe('cell-1')
    expect(t.result.current.state.placeName).toBe('Pinheiros')
    t.unmount()
  })

  it('does not post a nameless event, and says which box to fix', async () => {
    const createEvent = jest.fn()
    const t = mount(useCreateEvent, { resolveLocation: jest.fn(async () => located), createEvent } as unknown as Partial<UseCases>)
    await flush()
    let id: string | null = null
    await act(async () => void (id = await t.result.current.submit()))

    expect(id).toBeNull()
    expect(createEvent).not.toHaveBeenCalled()
    expect(t.result.current.state.errors.title).toBeTruthy()
    t.unmount()
  })

  it('posts what the host wrote and takes the reader to the event it made', async () => {
    const createEvent = jest.fn(async () => ok({ ...makeEvent('new'), at: null, distanceKm: null }))
    const t = mount(useCreateEvent, { resolveLocation: jest.fn(async () => located), createEvent } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void t.result.current.set(filled))
    let id: string | null = null
    await act(async () => void (id = await t.result.current.submit()))

    expect(createEvent).toHaveBeenCalledWith(expect.objectContaining({ title: 'Sunday market', locationCell: 'cell-1' }))
    expect(id).toBe('new')
    t.unmount()
  })

  it('steps the whole evening along with the start, so an end is never left behind', async () => {
    const t = mount(useCreateEvent, { resolveLocation: jest.fn(async () => located) } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void t.result.current.set({ ...filled, endsAt: new Date(2026, 10, 26, 22, 0) }))
    await act(async () => void t.result.current.shiftStart(3_600_000))

    expect(t.result.current.state.draft.startsAt?.getHours()).toBe(20)
    expect(t.result.current.state.draft.endsAt?.getHours()).toBe(23)
    t.unmount()
  })

  it('leaves the form alone to hear what the server said', async () => {
    const t = mount(useCreateEvent, {
      resolveLocation: jest.fn(async () => located),
      createEvent: jest.fn(async () => err('unexpected')),
    } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void t.result.current.set(filled))
    let id: string | null = null
    await act(async () => void (id = await t.result.current.submit()))

    expect(id).toBeNull()
    expect(t.result.current.state).toMatchObject({ busy: false })
    expect(t.result.current.state.error).toBeTruthy()
    t.unmount()
  })
})
