import { act, create } from 'react-test-renderer'

import type { UseCases } from '../../application'
import { err, ok, type FeedPage, type Post } from '../../domain'
import { makePost } from '../../testing/fakes'
import { UseCasesProvider } from '../use-cases'
import { useCompose } from '../use-compose'
import { useFeed } from '../use-feed'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

function mount<T>(hook: () => T, overrides: Partial<UseCases>) {
  const useCases = overrides as UseCases
  const result = { current: undefined as unknown as T }
  function Probe() {
    result.current = hook()
    return null
  }
  let renderer: ReturnType<typeof create>
  act(() => {
    renderer = create(
      <UseCasesProvider useCases={useCases}>
        <Probe />
      </UseCasesProvider>,
    )
  })
  return { result, unmount: () => act(() => renderer.unmount()) }
}

const located = ok({ cell: 'cell-1', placeName: 'Pinheiros' })
const page = (ids: string[], nextCursor: string | null): FeedPage => ({ posts: ids.map((id) => makePost(id)), nextCursor })

describe('useFeed', () => {
  function setup(extra: Partial<UseCases> = {}) {
    let push: (post: Post) => void = () => {}
    const unsubscribe = jest.fn()
    const loadFeed = jest.fn(async ({ cursor }: { cell: string; cursor?: string }) => ok(cursor ? page(['c', 'd'], null) : page(['a', 'b'], 'next')))
    const resolveLocation = jest.fn(async () => located)
    const subscribeToPosts = jest.fn((_cell: string, onPost: (post: Post) => void) => ((push = onPost), unsubscribe))
    const mounted = mount(useFeed, { loadFeed, resolveLocation, subscribeToPosts, ...extra } as Partial<UseCases>)
    return { ...mounted, loadFeed, resolveLocation, subscribeToPosts, unsubscribe, push: (p: Post) => act(() => push(p)) }
  }

  it('loads the feed for the located cell and subscribes to its stream', async () => {
    const t = setup()
    await flush()
    expect(t.resolveLocation).toHaveBeenCalledWith({ prompt: true })
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-1' })
    expect(t.subscribeToPosts).toHaveBeenCalledWith('cell-1', expect.any(Function))
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.placeName).toBe('Pinheiros')
    t.unmount()
    expect(t.unsubscribe).toHaveBeenCalled()
  })

  it('shows the location-off state when permission is denied', async () => {
    const t = setup({ resolveLocation: jest.fn(async () => err({ kind: 'denied' as const, canAskAgain: false })) })
    await flush()
    expect(t.result.current.state.phase).toBe('denied')
    expect(t.result.current.state.canAskAgain).toBe(false)
    expect(t.loadFeed).not.toHaveBeenCalled()
    expect(t.subscribeToPosts).not.toHaveBeenCalled()
  })

  it('loads the next page by cursor when scrolling to the end, without duplicates', async () => {
    const t = setup()
    await flush()
    await act(async () => t.result.current.loadMore())
    expect(t.loadFeed).toHaveBeenLastCalledWith({ cell: 'cell-1', cursor: 'next' })
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b', 'c', 'd'])
    expect(t.result.current.state.hasMore).toBe(false)
    await act(async () => t.result.current.loadMore())
    expect(t.loadFeed).toHaveBeenCalledTimes(2)
  })

  it('reloads from the first page on refresh', async () => {
    const t = setup()
    await flush()
    await act(async () => t.result.current.loadMore())
    await act(async () => t.result.current.refresh())
    expect(t.resolveLocation).toHaveBeenLastCalledWith({ prompt: false })
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.refreshing).toBe(false)
  })

  it('buffers streamed posts and prepends them on demand without reloading', async () => {
    const t = setup()
    await flush()
    t.push(makePost('n1'))
    t.push(makePost('n2'))
    t.push(makePost('n2'))
    t.push(makePost('a'))
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.pending.map((p) => p.id)).toEqual(['n2', 'n1'])
    act(() => t.result.current.showPending())
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['n2', 'n1', 'a', 'b'])
    expect(t.result.current.state.pending).toEqual([])
    expect(t.loadFeed).toHaveBeenCalledTimes(1)
  })
})

describe('useCompose', () => {
  function setup(opts: { location?: boolean; communities?: { id: string; name: string }[] } = {}) {
    const createPost = jest.fn(async () => ok(makePost('new')))
    const resolveLocation = jest.fn(async () => (opts.location === false ? err({ kind: 'denied' as const, canAskAgain: true }) : located))
    const listJoinedCommunities = jest.fn(async () => ok(opts.communities ?? []))
    return { ...mount(useCompose, { createPost, resolveLocation, listJoinedCommunities } as unknown as Partial<UseCases>), createPost, resolveLocation }
  }

  it('turns location on by default when permission is granted, without prompting', async () => {
    const t = setup()
    await flush()
    expect(t.resolveLocation).toHaveBeenCalledWith({ prompt: false })
    expect(t.result.current.location).toEqual({ cell: 'cell-1', placeName: 'Pinheiros' })
  })

  it('sends the location cell when location is on', async () => {
    const t = setup()
    await flush()
    act(() => t.result.current.setBody('hello'))
    await act(async () => void (await t.result.current.submit()))
    expect(t.createPost).toHaveBeenCalledWith({ body: 'hello', locationCell: 'cell-1', communityId: undefined })
  })

  it('omits the location cell after the location is cleared', async () => {
    const t = setup()
    await flush()
    act(() => t.result.current.setBody('hello'))
    act(() => t.result.current.clearLocation())
    expect(t.result.current.location).toBeNull()
    await act(async () => void (await t.result.current.submit()))
    expect(t.createPost).toHaveBeenCalledWith({ body: 'hello', locationCell: undefined, communityId: undefined })
  })

  it('has no location when permission is missing', async () => {
    const t = setup({ location: false })
    await flush()
    expect(t.result.current.location).toBeNull()
  })

  it('sends the chosen community and toggles it off again', async () => {
    const t = setup({ communities: [{ id: 'c1', name: 'Vizinhos' }] })
    await flush()
    expect(t.result.current.communities).toHaveLength(1)
    act(() => t.result.current.setBody('hi'))
    act(() => t.result.current.toggleCommunity('c1'))
    await act(async () => void (await t.result.current.submit()))
    expect(t.createPost).toHaveBeenLastCalledWith(expect.objectContaining({ communityId: 'c1' }))
    act(() => t.result.current.toggleCommunity('c1'))
    expect(t.result.current.communityId).toBeNull()
  })
})
