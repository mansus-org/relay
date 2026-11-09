import { act, create } from 'react-test-renderer'

import { err, ok, type Post, type Reaction, type ThreadEntry } from '../../domain'
import { makePost } from '../../testing/fakes'
import { UseCasesProvider } from '../use-cases'
import { useThread } from '../use-post'

const mockUser = { id: 'u1', name: 'me' }
jest.mock('../auth', () => ({ useAuth: () => ({ user: mockUser }) }))

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

function mount(overrides: Record<string, unknown>) {
  const hook = { current: undefined as unknown as ReturnType<typeof useThread> }
  /** The thread as the screen sees it. */
  const view = () => hook.current.state
  function Probe() {
    hook.current = useThread('root')
    return null
  }
  const tree = () => (
    <UseCasesProvider useCases={overrides as never}>
      <Probe />
    </UseCasesProvider>
  )
  let renderer: ReturnType<typeof create>
  act(() => {
    renderer = create(tree())
  })
  return { view, hook, rerender: () => act(() => renderer.update(tree())) }
}

const said = (id: string, overrides: Partial<Post> = {}) => makePost(id, { parentId: 'root', ...overrides })

/** The ids on screen, in order, with how far each sits from the post that started it. */
const shape = (entries: readonly ThreadEntry[]) => entries.map((e) => `${e.post.id}@${e.depth}${e.open ? '+' : ''}`)

function setup(overrides: Record<string, unknown> = {}) {
  const loadThread = jest.fn(async () => ok(makePost('root', { replyCount: 2 })))
  const loadReplies = jest.fn(async (postId: string) => ok([said(`${postId}a`, { parentId: postId }), said(`${postId}b`, { parentId: postId, replyCount: 1 })]))
  const reply = jest.fn(async ({ body }: { parentId: string; body: string }) => ok(said('server', { body, parentId: 'root' })))
  const toggleReaction = jest.fn(async () => ok({ emoji: '🔥', count: 7, mine: true } as Reaction))
  const t = mount({ loadThread, loadReplies, reply, toggleReaction, ...overrides })
  return {
    loadThread,
    loadReplies,
    reply,
    toggleReaction,
    /** The post with this id, as it stands on screen. */
    post: (id: string) => t.view().entries.find((e) => e.post.id === id)!.post,
    ...t,
  }
}

describe('useThread', () => {
  it('reads the post and the level of replies straight under it', async () => {
    const t = setup()
    await flush()
    expect(t.loadThread).toHaveBeenCalledWith('root')
    expect(t.loadReplies).toHaveBeenCalledWith('root')
    expect(t.view().loaded).toBe(true)
    expect(t.view().failed).toBe(false)
    expect(shape(t.view().entries)).toEqual(['root@0+', 'roota@1', 'rootb@1'])
  })

  it('does not go looking for replies a post does not have', async () => {
    const t = setup({ loadThread: jest.fn(async () => ok(makePost('root'))) })
    await flush()
    expect(t.loadReplies).not.toHaveBeenCalled()
    expect(shape(t.view().entries)).toEqual(['root@0'])
  })

  it('says the thread is gone when the post will not load', async () => {
    const t = setup({ loadThread: jest.fn(async () => err({ status: 404 })) })
    await flush()
    expect(t.view().loaded).toBe(true)
    expect(t.view().failed).toBe(true)
    expect(t.view().entries).toEqual([])
    expect(t.loadReplies).not.toHaveBeenCalled()
  })

  it('closes the replies it opened, and asks for them again when reopened', async () => {
    const t = setup()
    await flush()

    await act(async () => void (await t.hook.current.toggleReplies(makePost('root', { replyCount: 2 }))))
    expect(shape(t.view().entries)).toEqual(['root@0'])

    await act(async () => void (await t.hook.current.toggleReplies(makePost('root', { replyCount: 2 }))))
    expect(t.loadReplies).toHaveBeenCalledTimes(2)
    expect(shape(t.view().entries)).toEqual(['root@0+', 'roota@1', 'rootb@1'])
  })

  it('opens one more level when asked, and no further', async () => {
    const t = setup()
    await flush()
    await act(async () => void (await t.hook.current.toggleReplies(makePost('rootb', { replyCount: 1 }))))
    expect(t.loadReplies).toHaveBeenLastCalledWith('rootb')
    expect(shape(t.view().entries)).toEqual(['root@0+', 'roota@1', 'rootb@1+', 'rootba@2', 'rootbb@2'])
  })

  it('says when replies will not load, and shows nothing new', async () => {
    const t = setup({ loadReplies: jest.fn(async () => err({ status: 500 })) })
    await flush()
    expect(t.view().entries.length).toBe(1)
    expect(t.view().problem).toBeTruthy()
  })

  it('puts a reaction on at once and keeps whatever the server counted', async () => {
    const t = setup()
    await flush()
    const root = t.post('root')
    act(() => void t.hook.current.toggleReaction(root, '🔥'))
    expect(t.post('root').reactions).toEqual([{ emoji: '🔥', count: 1, mine: true }])
    await flush()
    expect(t.toggleReaction).toHaveBeenCalledWith(root, '🔥')
    expect(t.post('root').reactions).toEqual([{ emoji: '🔥', count: 7, mine: true }])
  })

  it('takes a reaction back when the server refuses it', async () => {
    const t = setup({ toggleReaction: jest.fn(async () => err({ status: 500 })) })
    await flush()
    await act(async () => void (await t.hook.current.toggleReaction(t.post('root'), '🔥')))
    expect(t.post('root').reactions).toEqual([])
    expect(t.view().problem).toBeTruthy()
  })

  it('sends a reply to whoever the bar is on, and swaps the placeholder for what came back', async () => {
    const t = setup()
    await flush()
    act(() => t.hook.current.askReplyTo('roota'))
    expect(t.view().replyingTo?.post.id).toBe('roota')

    act(() => void t.hook.current.sendReply('  agreed  '))
    expect(t.view().entries.map((e) => e.post.body)).toContain('agreed')
    expect(t.view().replyingTo).toBeNull()
    await flush()
    expect(t.reply).toHaveBeenCalledWith({ parentId: 'roota', body: 'agreed' })
    const sent = t.view().entries.find((e) => e.post.body === 'agreed')
    expect(sent?.post.id).toBe('server')
    expect(sent?.depth).toBe(2)
  })

  it('takes a reply back off when it did not go through', async () => {
    const t = setup({ reply: jest.fn(async () => err({ status: 500 })) })
    await flush()
    await act(async () => void (await t.hook.current.sendReply('nope')))
    expect(t.view().entries.some((e) => e.post.body === 'nope')).toBe(false)
    expect(t.view().problem).toBeTruthy()
  })

  it('closes the replies a reply opened for good, when that reply fails', async () => {
    const t = setup({ reply: jest.fn(async () => err({ status: 500 })) })
    await flush()
    act(() => t.hook.current.askReplyTo('roota'))
    await act(async () => void (await t.hook.current.sendReply('nope')))
    expect(shape(t.view().entries)).toEqual(['root@0+', 'roota@1', 'rootb@1'])
  })

  it('sends nothing when there is nothing to send', async () => {
    const t = setup()
    await flush()
    expect(await t.hook.current.sendReply('   ')).toBe(false)
    expect(t.reply).not.toHaveBeenCalled()
    expect(shape(t.view().entries)).toEqual(['root@0+', 'roota@1', 'rootb@1'])
  })
})
