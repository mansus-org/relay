import { act, create } from 'react-test-renderer'
import { Platform } from 'react-native'

import { makeReadPostalCode, makeResolvePostalCode, type LocationError, type ResolvedLocation, type UseCases } from '../../application'
import { err, ok, type FeedPage, type Post, type Result } from '../../domain'
import { makeFakePostalCodeResolver, makePostalArea, makePost } from '../../testing/fakes'
import { UseCasesProvider } from '../use-cases'
import { useCompose } from '../use-compose'
import { useFeed, type FeedOptions } from '../use-feed'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

function mount<T>(hook: () => T, overrides: Partial<UseCases>) {
  const useCases = overrides as UseCases
  const result = { current: undefined as unknown as T }
  function Probe() {
    result.current = hook()
    return null
  }
  const tree = () => (
    <UseCasesProvider useCases={useCases}>
      <Probe />
    </UseCasesProvider>
  )
  let renderer: ReturnType<typeof create>
  act(() => {
    renderer = create(tree())
  })
  return { result, rerender: () => act(() => renderer.update(tree())), unmount: () => act(() => renderer.unmount()) }
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

describe('useFeed on the web', () => {
  const platform = Platform as unknown as { OS: string }
  const native = platform.OS

  beforeAll(() => void (platform.OS = 'web'))
  afterAll(() => void (platform.OS = native))

  /** What the browser answers when it will not say: no position, and no point in asking it again. */
  const refused = err({ kind: 'denied' as const, canAskAgain: false })

  function setup(
    saved: string | null = null,
    initial: FeedOptions = {},
    browser: Result<ResolvedLocation, LocationError> = refused,
    hold = false,
  ) {
    let code = saved
    let options = initial
    let answer = browser
    /** Set when the browser is made to wait, so the test can answer it whenever it likes. */
    let release: ((next: Result<ResolvedLocation, LocationError>) => void) | null = null
    const store = { read: async () => code, save: async (next: string) => void (code = next) }
    const resolver = makeFakePostalCodeResolver(
      { '36201': makePostalArea('36201', 'Vigo', 'cell-vigo'), '15003': makePostalArea('15003', 'A Coruña', 'cell-coruna') },
      { reason: 'not-found', message: "32999 is not in Relay's data yet." },
    )
    const unsubscribe = jest.fn()
    const loadFeed = jest.fn(async ({ cursor }: { cell: string; cursor?: string }) => ok(cursor ? page(['c', 'd'], null) : page(['a', 'b'], 'next')))
    const resolveLocation = jest.fn(
      () =>
        new Promise<Result<ResolvedLocation, LocationError>>((resolve) => {
          if (hold) release = resolve
          else resolve(answer)
        }),
    )
    const subscribeToPosts = jest.fn(() => unsubscribe)
    const mounted = mount(() => useFeed(options), {
      loadFeed,
      resolveLocation,
      subscribeToPosts,
      resolvePostalCode: makeResolvePostalCode({ resolver, store }),
      readPostalCode: makeReadPostalCode({ store }),
    } as Partial<UseCases>)
    const submit = (raw: string) => {
      act(() => mounted.result.current.setPostalCode(raw))
      return flush()
    }
    // The feed screen hands the hook a new options object on every render, so the tests can too.
    const setPlaced = (onPlaced: (code: string) => void) => {
      options = { ...options, onPlaced }
      act(() => {
        mounted.rerender()
      })
    }
    /** Change what the browser answers, partway through. */
    const answerWith = (next: Result<ResolvedLocation, LocationError>) => void (answer = next)
    /** The browser answers late: after the person has already moved on without it. */
    const answerLater = (next: Result<ResolvedLocation, LocationError>) => {
      act(() => release!(next))
      return flush()
    }
    const pressLocation = () => {
      act(() => void mounted.result.current.useBrowserLocation())
      return flush()
    }
    return { ...mounted, submit, setPlaced, pressLocation, answerWith, answerLater, loadFeed, resolveLocation, resolver, saved: () => code }
  }

  it('opens on where the browser says it is, without asking for a place', async () => {
    const t = setup(null, {}, located)
    await flush()
    expect(t.resolveLocation).toHaveBeenCalledWith({ prompt: true })
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.result.current.state.placeName).toBe('Pinheiros')
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-1' })
    // Nothing to look up when the browser answered: the server never sees a code.
    expect(t.resolver.calls).toEqual([])
  })

  it('opens on the browser position over the place it remembers', async () => {
    const t = setup('36201', {}, located)
    await flush()
    expect(t.result.current.state.placeName).toBe('Pinheiros')
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-1' })
  })

  it('falls back to the place it remembers when the browser will not say', async () => {
    const t = setup('36201')
    await flush()
    expect(t.resolveLocation).toHaveBeenCalledWith({ prompt: true })
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.result.current.state.placeName).toBe('Vigo')
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
  })

  it('asks for a postal code when neither the browser nor the person has a place', async () => {
    const t = setup()
    await flush()
    expect(t.result.current.state.phase).toBe('ask')
    expect(t.loadFeed).not.toHaveBeenCalled()
  })

  it('does not ask the browser when the address already names the place', async () => {
    const t = setup('36201', { requestedCode: '15003' }, located)
    await flush()
    expect(t.resolveLocation).not.toHaveBeenCalled()
    expect(t.result.current.state.placeName).toBe('A Coruña')
  })

  it('asks the browser again from the prompt, and says when it still will not say', async () => {
    const t = setup()
    await flush()
    await t.pressLocation()
    expect(t.resolveLocation).toHaveBeenCalledTimes(2)
    expect(t.result.current.state.phase).toBe('ask')
    expect(t.result.current.state.askingBrowser).toBe(false)
    expect(t.result.current.state.placeError).toBe('Your browser would not say where you are. Try a postal code.')
  })

  it('opens the feed when the browser answers the second ask', async () => {
    const t = setup()
    await flush()
    t.answerWith(located)
    await t.pressLocation()
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.result.current.state.placeName).toBe('Pinheiros')
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-1' })
  })

  it('reads the feed of a typed code and keeps it for next time', async () => {
    const t = setup()
    await flush()
    await t.submit('15003')
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-coruna' })
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.saved()).toBe('15003')
  })

  it('says why a code was refused and keeps asking', async () => {
    const t = setup()
    await flush()
    await t.submit('32999')
    expect(t.result.current.state.phase).toBe('ask')
    expect(t.result.current.state.placeError).toBe("32999 is not in Relay's data yet.")
    expect(t.loadFeed).not.toHaveBeenCalled()
  })

  it('does not ask the server for a code that is not five digits', async () => {
    const t = setup()
    await flush()
    await t.submit('36')
    expect(t.resolver.calls).toEqual([])
    expect(t.result.current.state.placeError).toBe('Postal codes are 5 digits.')
  })

  it('keeps the last good place when a new code fails', async () => {
    const t = setup('36201')
    await flush()
    await t.submit('32999')
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
    expect(t.result.current.state.placeError).toBe("32999 is not in Relay's data yet.")
  })

  it('leaves for the prompt and comes back without reloading', async () => {
    const t = setup('36201')
    await flush()
    act(() => t.result.current.changePlace())
    expect(t.result.current.state.phase).toBe('ask')
    act(() => t.result.current.backToFeed())
    expect(t.result.current.state.phase).toBe('ready')
    expect(t.loadFeed).toHaveBeenCalledTimes(1)
  })

  it('keeps the place the person typed while the browser was still thinking', async () => {
    const t = setup(null, {}, refused, true)
    await flush()
    act(() => t.result.current.changePlace())
    await t.submit('36201')
    expect(t.result.current.state.placeName).toBe('Vigo')
    await t.answerLater(located)
    // The browser had its say too late: Vigo is still on screen.
    expect(t.result.current.state.placeName).toBe('Vigo')
    expect(t.loadFeed).not.toHaveBeenCalledWith({ cell: 'cell-1' })
  })

  it('refreshes the place it fell back to, instead of asking the browser again', async () => {
    const t = setup('36201')
    await flush()
    await act(async () => t.result.current.loadMore())
    await act(async () => t.result.current.refresh())
    expect(t.resolveLocation).toHaveBeenCalledTimes(1)
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
  })

  it('refreshes through the browser when that is where the feed opened', async () => {
    const t = setup(null, {}, located)
    await flush()
    await act(async () => t.result.current.refresh())
    expect(t.resolveLocation).toHaveBeenCalledTimes(2)
    expect(t.loadFeed).toHaveBeenCalledTimes(2)
  })

  it('falls back to the prompt when the browser stops answering and nothing was remembered', async () => {
    const t = setup(null, {}, located)
    await flush()
    t.answerWith(refused)
    await act(async () => t.result.current.refresh())
    expect(t.result.current.state.phase).toBe('ask')
    expect(t.result.current.state.placeError).toBe('Your browser would not say where you are. Try a postal code.')
  })

  it('opens on the place the address names, not the one it remembers', async () => {
    const t = setup('36201', { requestedCode: '15003' })
    await flush()
    expect(t.result.current.state.placeName).toBe('A Coruña')
    expect(t.loadFeed).toHaveBeenCalledWith({ cell: 'cell-coruna' })
    expect(t.saved()).toBe('15003')
  })

  it('reads the address once: a code that goes away does not move the feed', async () => {
    const t = setup(null, { requestedCode: '15003' })
    await flush()
    await t.submit('36201')
    expect(t.loadFeed).toHaveBeenCalledTimes(2)
    t.setPlaced(() => {})
    await flush()
    expect(t.result.current.state.placeName).toBe('Vigo')
    expect(t.loadFeed).toHaveBeenCalledTimes(2)
  })

  it('says which place it opened, so the address can follow it', async () => {
    const placed = jest.fn()
    const t = setup('36201', { onPlaced: placed })
    await flush()
    expect(placed).toHaveBeenCalledWith('36201')
    await t.submit('15003')
    expect(placed).toHaveBeenLastCalledWith('15003')
  })

  it('does not reload when the caller hands over a new callback', async () => {
    const t = setup('36201')
    await flush()
    expect(t.loadFeed).toHaveBeenCalledTimes(1)
    t.setPlaced(() => {})
    await flush()
    expect(t.loadFeed).toHaveBeenCalledTimes(1)
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['a', 'b'])
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
