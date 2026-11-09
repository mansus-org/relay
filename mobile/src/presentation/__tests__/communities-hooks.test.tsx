import { act, create } from 'react-test-renderer'

import type { UseCases } from '../../application'
import { err, ok, type Event, type NearbyCommunity } from '../../domain'
import { makeCommunity, makePost } from '../../testing/fakes'
import { UseCasesProvider } from '../use-cases'
import { useCommunity } from '../use-community'
import { useCreateCommunity } from '../use-create-community'
import { useNearbyCommunities } from '../use-nearby-communities'

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
const nearby = (id: string, overrides: Partial<NearbyCommunity> = {}): NearbyCommunity => ({
  ...makeCommunity(id),
  distanceKm: 1,
  inRange: true,
  ...overrides,
})

describe('useNearbyCommunities', () => {
  it('loads the communities for the located cell, in the order the use case returns them', async () => {
    const loadNearbyCommunities = jest.fn(async () => ok([nearby('near', { distanceKm: 1 }), nearby('far', { distanceKm: 30, inRange: false })]))
    const t = mount(useNearbyCommunities, { resolveLocation: jest.fn(async () => located), loadNearbyCommunities } as unknown as Partial<UseCases>)
    await flush()
    expect(loadNearbyCommunities).toHaveBeenCalledWith({ cell: 'cell-1' })
    const { state } = t.result.current
    expect(state.phase).toBe('ready')
    expect(state.placeName).toBe('Pinheiros')
    expect(state.communities.map((c) => [c.id, c.inRange])).toEqual([
      ['near', true],
      ['far', false],
    ])
  })

  it('shows the denied state without loading when location permission is missing', async () => {
    const loadNearbyCommunities = jest.fn()
    const resolveLocation = jest.fn(async () => err({ kind: 'denied' as const, canAskAgain: false }))
    const t = mount(useNearbyCommunities, { resolveLocation, loadNearbyCommunities } as unknown as Partial<UseCases>)
    await flush()
    expect(t.result.current.state.phase).toBe('denied')
    expect(loadNearbyCommunities).not.toHaveBeenCalled()
  })

  it('flags a failed load', async () => {
    const t = mount(useNearbyCommunities, {
      resolveLocation: jest.fn(async () => located),
      loadNearbyCommunities: jest.fn(async () => err('network' as const)),
    } as unknown as Partial<UseCases>)
    await flush()
    expect(t.result.current.state.failed).toBe(true)
  })
})

describe('useCommunity', () => {
  const event = (id: string): Event => ({
    id,
    hostId: 'u-1',
    hostName: 'Ana',
    title: `Event ${id}`,
    startsAt: '2026-11-25T19:30:00+00:00',
    endsAt: null,
    venueName: null,
    details: null,
    locationCell: null,
    communityId: 'c1',
    communityName: 'Vila',
    rsvpCount: 2,
  })

  function setup(opts: {
    community?: Partial<NearbyCommunity>
    joinResult?: 'ok' | 'out-of-range'
    location?: boolean
    events?: 'ok' | 'pages' | 'error'
  } = {}) {
    let member = opts.community?.isMember ?? false
    const resolveLocation = jest.fn(async () => (opts.location === false ? err({ kind: 'denied' as const, canAskAgain: true }) : located))
    const loadCommunity = jest.fn(async () => ok(nearby('c1', { ...opts.community, isMember: member })))
    const loadCommunityFeed = jest.fn(async ({ cursor }: { communityId: string; cursor?: string }) =>
      member
        ? ok({ posts: cursor ? [makePost('c')] : [makePost('a'), makePost('b')], nextCursor: cursor ? null : 'next' })
        : err('forbidden' as const),
    )
    const loadCommunityEvents = jest.fn(async ({ from }: { communityId: string; cell?: string | null; from?: string }) => {
      if (opts.events === 'error') return err('network' as const)
      if (opts.events === 'pages') return ok({ events: from ? [event('3')] : [event('1'), event('2')], nextFrom: from ? null : 'next' })
      return ok({ events: [event('1')], nextFrom: null })
    })
    const joinCommunity = jest.fn(async () => {
      if (opts.joinResult === 'out-of-range') return err('out-of-range' as const)
      member = true
      return ok(undefined)
    })
    const mounted = mount(() => useCommunity('c1'), {
      resolveLocation,
      loadCommunity,
      loadCommunityFeed,
      loadCommunityEvents,
      joinCommunity,
    } as unknown as Partial<UseCases>)
    return { ...mounted, loadCommunity, loadCommunityFeed, loadCommunityEvents, joinCommunity }
  }

  it('does not load the feed of a community the user has not joined', async () => {
    const t = setup()
    await flush()
    expect(t.loadCommunity).toHaveBeenCalledWith({ id: 'c1', cell: 'cell-1' })
    expect(t.result.current.state.community?.isMember).toBe(false)
    expect(t.result.current.canJoin).toBe(true)
    expect(t.loadCommunityFeed).not.toHaveBeenCalled()
  })

  it('joins with the current cell and loads the feed afterwards', async () => {
    const t = setup()
    await flush()
    await act(async () => t.result.current.requestJoin())
    expect(t.joinCommunity).toHaveBeenCalledWith({ communityId: 'c1', cell: 'cell-1', pseudonym: undefined })
    expect(t.result.current.state.community).toMatchObject({ isMember: true, memberCount: 11 })
    expect(t.loadCommunityFeed).toHaveBeenCalledWith({ communityId: 'c1' })
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.canJoin).toBe(false)
  })

  it('asks for a pseudonym first when the community allows them, then sends it', async () => {
    const t = setup({ community: { allowPseudonyms: true } })
    await flush()
    await act(async () => t.result.current.requestJoin())
    expect(t.result.current.promptOpen).toBe(true)
    expect(t.joinCommunity).not.toHaveBeenCalled()
    await act(async () => t.result.current.join('sambista_vm'))
    expect(t.joinCommunity).toHaveBeenCalledWith({ communityId: 'c1', cell: 'cell-1', pseudonym: 'sambista_vm' })
    expect(t.result.current.promptOpen).toBe(false)
    expect(t.result.current.state.community?.isMember).toBe(true)
  })

  it('can join under the real name from the pseudonym sheet', async () => {
    const t = setup({ community: { allowPseudonyms: true } })
    await flush()
    await act(async () => t.result.current.requestJoin())
    await act(async () => t.result.current.join())
    expect(t.joinCommunity).toHaveBeenCalledWith({ communityId: 'c1', cell: 'cell-1', pseudonym: undefined })
  })

  it('cannot join a community out of range, or without a position', async () => {
    const far = setup({ community: { inRange: false, distanceKm: 40 } })
    await flush()
    expect(far.result.current.canJoin).toBe(false)
    await act(async () => far.result.current.requestJoin())
    expect(far.joinCommunity).not.toHaveBeenCalled()

    const lost = setup({ location: false })
    await flush()
    expect(lost.result.current.state.noLocation).toBe(true)
    expect(lost.result.current.canJoin).toBe(false)
  })

  it('reports a refused join and stays a non-member', async () => {
    const t = setup({ joinResult: 'out-of-range' })
    await flush()
    await act(async () => t.result.current.requestJoin())
    expect(t.result.current.joinError).toBe('out-of-range')
    expect(t.result.current.state.community?.isMember).toBe(false)
    expect(t.loadCommunityFeed).not.toHaveBeenCalled()
  })

  it('loads the feed of a member by cursor without duplicates', async () => {
    const t = setup({ community: { isMember: true } })
    await flush()
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.hasMore).toBe(true)
    await act(async () => t.result.current.loadMore())
    expect(t.loadCommunityFeed).toHaveBeenLastCalledWith({ communityId: 'c1', cursor: 'next' })
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b', 'c'])
    await act(async () => t.result.current.loadMore())
    expect(t.loadCommunityFeed).toHaveBeenCalledTimes(2)
  })

  it('reloads from the first page on refresh', async () => {
    const t = setup({ community: { isMember: true } })
    await flush()
    await act(async () => t.result.current.loadMore())
    await act(async () => t.result.current.refresh())
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.refreshing).toBe(false)
  })

  it('shows the community’s events to anyone, member or not', async () => {
    const t = setup()
    await flush()
    expect(t.loadCommunityEvents).toHaveBeenCalledWith({ communityId: 'c1', cell: 'cell-1' })
    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['1'])
    expect(t.result.current.state.eventsLoaded).toBe(true)
  })

  it('pages the events with the cursor it was handed, and does not ask again once there is no more', async () => {
    const t = setup({ events: 'pages' })
    await flush()
    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['1', '2'])
    await act(async () => t.result.current.loadMoreEvents())
    expect(t.loadCommunityEvents).toHaveBeenLastCalledWith({ communityId: 'c1', cell: 'cell-1', from: 'next' })
    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['1', '2', '3'])
    await act(async () => t.result.current.loadMoreEvents())
    expect(t.loadCommunityEvents).toHaveBeenCalledTimes(2)
  })

  it('says the events did not load, and tries again on a refresh', async () => {
    const t = setup({ events: 'error' })
    await flush()
    expect(t.result.current.state).toMatchObject({ eventsLoaded: true, eventsFailed: true, events: [] })
    t.loadCommunityEvents.mockResolvedValue(ok({ events: [event('9')], nextFrom: null }))
    await act(async () => t.result.current.refresh())
    expect(t.result.current.state.events.map((e) => e.id)).toEqual(['9'])
    expect(t.result.current.state.eventsFailed).toBe(false)
  })

  it('leaves the events alone when there is no position to read them from', async () => {
    const t = setup({ location: false })
    await flush()
    expect(t.loadCommunityEvents).not.toHaveBeenCalled()
    expect(t.result.current.state).toMatchObject({ eventsLoaded: true, eventsFailed: false, events: [] })
    await act(async () => t.result.current.loadMoreEvents())
    expect(t.loadCommunityEvents).not.toHaveBeenCalled()
  })
})

describe('useCreateCommunity', () => {
  function setup(opts: { location?: boolean } = {}) {
    const createCommunity = jest.fn(async () => ok(makeCommunity('new')))
    const resolveLocation = jest.fn(async () => (opts.location === false ? err({ kind: 'denied' as const, canAskAgain: true }) : located))
    return { ...mount(useCreateCommunity, { createCommunity, resolveLocation } as unknown as Partial<UseCases>), createCommunity }
  }

  it('sends the device cell by default, with the chosen radius and pseudonym setting', async () => {
    const t = setup()
    await flush()
    expect(t.result.current.useLocation).toBe(true)
    expect(t.result.current.placeName).toBe('Pinheiros')
    act(() => {
      t.result.current.setName('Vila Madalena Cultura')
      t.result.current.setDescription('Shows e feiras')
      t.result.current.setRadiusKm(12)
      t.result.current.setAllowPseudonyms(true)
    })
    await act(async () => void (await t.result.current.submit()))
    expect(t.createCommunity).toHaveBeenCalledWith({
      name: 'Vila Madalena Cultura',
      description: 'Shows e feiras',
      locationCell: 'cell-1',
      radiusKm: 12,
      allowPseudonyms: true,
    })
  })

  it('omits the location cell when "Use my current location" is off', async () => {
    const t = setup()
    await flush()
    act(() => {
      t.result.current.setName('Online group')
      t.result.current.setUseLocation(false)
    })
    await act(async () => void (await t.result.current.submit()))
    expect(t.createCommunity).toHaveBeenCalledWith(expect.objectContaining({ name: 'Online group', locationCell: undefined }))
  })

  it('clamps the radius to 1–50 km', async () => {
    const t = setup()
    await flush()
    act(() => t.result.current.setRadiusKm(120))
    expect(t.result.current.radiusKm).toBe(50)
    act(() => t.result.current.setRadiusKm(0))
    expect(t.result.current.radiusKm).toBe(1)
  })

  it('does not create with the toggle on while the position is unknown', async () => {
    const t = setup({ location: false })
    await flush()
    act(() => t.result.current.setName('x'))
    await act(async () => void (await t.result.current.submit()))
    expect(t.createCommunity).not.toHaveBeenCalled()
    expect(t.result.current.error).toBe('no-location')
  })

  it('reports validation errors from the use case', async () => {
    const createCommunity = jest.fn(async () => err('empty-name' as const))
    const t = mount(useCreateCommunity, { createCommunity, resolveLocation: jest.fn(async () => located) } as unknown as Partial<UseCases>)
    await flush()
    await act(async () => void (await t.result.current.submit()))
    expect(t.result.current.error).toBe('empty-name')
  })
})
