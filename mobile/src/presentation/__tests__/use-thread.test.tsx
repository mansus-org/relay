import { act, create } from 'react-test-renderer'

import type { UseCases } from '../../application'
import { err, ok, type ApiError, type Post, type Reaction, type Result, type ThreadEntry } from '../../domain'
import { makePost } from '../../testing/fakes'
import { AuthProvider } from '../auth'
import { UseCasesProvider } from '../use-cases'
import { useThread } from '../use-post'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// The auth provider sends a stranger to the login screen when the session dies; the router it
// would use is stubbed here.
jest.mock('expo-router', () => ({ useRouter: () => ({ replace: jest.fn() }) }))

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

/** Starts something the hook does and lets whatever it put on screen at once land. */
const tap = (fn: () => unknown) => act(() => void fn())

const user = { id: 'u1', name: 'bruno' }
const tally = (emoji: string, count: number, mine = false): Reaction => ({ emoji, count, mine })

/** The thread as it reads on screen: each post, its depth, and a star while its replies are open. */
const shape = (entries: readonly ThreadEntry[]): string =>
  entries.map((e) => `${e.post.id}${e.depth}${e.open ? '*' : ''}`).join(' ')

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

function setup(overrides: Partial<UseCases> = {}) {
  const root = makePost('p')
  const useCases = {
    restoreSession: jest.fn(async () => user),
    sessionEvents: { onExpired: () => () => undefined },
    loadThread: jest.fn(async () => ok(root)),
    loadReplies: jest.fn(async () => ok([] as readonly Post[])),
    reply: jest.fn(async () => ok(makePost('real', { parentId: 'p' }))),
    toggleReaction: jest.fn(async () => ok(tally('👍', 1, true))),
    ...overrides,
  } as unknown as UseCases

  const result = { current: undefined as unknown as ReturnType<typeof useThread> }
  function Probe() {
    result.current = useThread('p')
    return null
  }
  const tree = () => (
    <UseCasesProvider useCases={useCases}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </UseCasesProvider>
  )
  let renderer!: ReturnType<typeof create>
  act(() => {
    renderer = create(tree())
  })

  return {
    result,
    root,
    unmount: () => act(() => renderer.unmount()),
    state: () => result.current.state,
    entries: () => shape(result.current.state.entries),
    post: (id: string): Post => result.current.state.entries.find((e) => e.post.id === id)!.post,
  }
}

describe('useThread', () => {
  it('reads the post and shows it on its own', async () => {
    const t = setup()
    await flush()
    expect(t.state()).toMatchObject({ loaded: true, failed: false })
    expect(t.entries()).toBe('p0')
    t.unmount()
  })

  it('says the thread could not be read', async () => {
    const t = setup({ loadThread: jest.fn(async () => err('network' as const)) })
    await flush()
    expect(t.state()).toMatchObject({ loaded: true, failed: true })
    expect(t.entries()).toBe('')
    t.unmount()
  })

  it('shows one level of replies under the post, and hides them again', async () => {
    const loadReplies = jest.fn(async () => ok([makePost('a'), makePost('b')]))
    const t = setup({ loadReplies })
    await flush()

    tap(() => t.result.current.toggleReplies(t.root))
    await flush()
    expect(t.entries()).toBe('p0* a1 b1')
    expect(loadReplies).toHaveBeenCalledWith('p')

    tap(() => t.result.current.toggleReplies(t.post('p')))
    await flush()
    expect(t.entries()).toBe('p0')
    expect(loadReplies).toHaveBeenCalledTimes(1)
    expect(t.state().loadingRepliesFor).toBeNull()
    t.unmount()
  })

  it('nests a reply under the reply it answers', async () => {
    const t = setup({
      loadReplies: jest.fn(async (postId: string) => ok(postId === 'p' ? [makePost('a')] : [makePost('c')])),
    })
    await flush()
    tap(() => t.result.current.toggleReplies(t.root))
    await flush()
    tap(() => t.result.current.toggleReplies(t.post('a')))
    await flush()
    expect(t.entries()).toBe('p0* a1* c2')
    t.unmount()
  })

  it('says the replies would not load and shows nothing new', async () => {
    const t = setup({ loadReplies: jest.fn(async () => err('network' as const)) })
    await flush()
    tap(() => t.result.current.toggleReplies(t.root))
    await flush()
    expect(t.entries()).toBe('p0')
    expect(t.state().problem).toBeTruthy()
    t.unmount()
  })

  it('shows an emoji the moment it is tapped and keeps what the server counted', async () => {
    const server = deferred<Result<Reaction, ApiError>>()
    const t = setup({ toggleReaction: jest.fn(() => server.promise) })
    await flush()

    tap(() => t.result.current.toggleReaction(t.root, '👍'))
    expect(t.post('p').reactions).toEqual([tally('👍', 1, true)])

    server.resolve(ok(tally('👍', 7, true)))
    await flush()
    expect(t.post('p').reactions).toEqual([tally('👍', 7, true)])
    expect(t.state().problem).toBeNull()
    t.unmount()
  })

  it('puts the emoji back when the server refuses it', async () => {
    const t = setup({ toggleReaction: jest.fn(async () => err('network' as const)) })
    await flush()
    tap(() => t.result.current.toggleReaction(t.root, '🔥'))
    await flush()
    expect(t.post('p').reactions).toEqual([])
    expect(t.state().problem).toBeTruthy()
    t.unmount()
  })

  it('takes your emoji back and keeps the tally of the ones left', async () => {
    const left = makePost('p', { reactions: [tally('👍', 3, true)] })
    const t = setup({
      loadThread: jest.fn(async () => ok(left)),
      toggleReaction: jest.fn(async () => ok(tally('👍', 2, false))),
    })
    await flush()
    tap(() => t.result.current.toggleReaction(left, '👍'))
    await flush()
    expect(t.post('p').reactions).toEqual([tally('👍', 2, false)])
    t.unmount()
  })

  it('shows a reply before the server has answered, then the one it sent back', async () => {
    const server = deferred<Result<Post, ApiError>>()
    const reply = jest.fn(() => server.promise)
    const t = setup({ reply })
    await flush()
    tap(() => t.result.current.askReplyTo(null))

    tap(() => void t.result.current.sendReply('  nice  '))
    expect(t.entries()).toBe('p0* pending-11')
    expect(t.state().sending).toBe(true)
    expect(reply).toHaveBeenCalledWith({ parentId: 'p', body: '  nice  ' })

    server.resolve(ok(makePost('real', { parentId: 'p', body: 'nice' })))
    await flush()
    expect(t.entries()).toBe('p0* real1')
    expect(t.state()).toMatchObject({ sending: false, problem: null, replyingTo: null })
    t.unmount()
  })

  it('takes a reply that did not go through back off the screen and says why', async () => {
    const t = setup({ reply: jest.fn(async () => err('network' as const)) })
    await flush()
    tap(() => t.result.current.askReplyTo(null))

    let answered = false
    tap(() => void t.result.current.sendReply('nope').then((ok_) => (answered = ok_)))
    await flush()
    expect(answered).toBe(false)
    expect(t.entries()).toBe('p0')
    expect(t.state().problem).toBeTruthy()
    t.unmount()
  })

  it('writes a reply to the post that was tapped', async () => {
    const reply = jest.fn(async () => ok(makePost('real', { parentId: 'a' })))
    const t = setup({ loadReplies: jest.fn(async () => ok([makePost('a')])), reply })
    await flush()
    tap(() => t.result.current.toggleReplies(t.root))
    await flush()
    tap(() => t.result.current.askReplyTo('a'))
    expect(t.state().replyingTo?.post.id).toBe('a')

    tap(() => void t.result.current.sendReply('under a'))
    await flush()
    expect(reply).toHaveBeenCalledWith({ parentId: 'a', body: 'under a' })
    expect(t.entries()).toBe('p0* a1* real2')
    t.unmount()
  })

  it('moves the reply bar to the post tapped and closes it again', async () => {
    const t = setup()
    await flush()
    tap(() => t.result.current.askReplyTo('p'))
    expect(t.state().replyingTo?.post.id).toBe('p')
    tap(() => t.result.current.cancelReply())
    expect(t.state().replyingTo).toBeNull()
    t.unmount()
  })
})
