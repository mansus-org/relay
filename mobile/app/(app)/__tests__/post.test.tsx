import { act, create } from 'react-test-renderer'
import type { ReactNode } from 'react'

import { err, ok, type Post, type Reaction, type Result } from '../../../src/domain'
import { AuthProvider } from '../../../src/presentation/auth'
import { UseCasesProvider } from '../../../src/presentation/use-cases'
import { makePost } from '../../../src/testing/fakes'

import Thread from '../post/[id]'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

jest.mock('expo-router', () => {
  const state = { params: { id: 'root' } as Record<string, string>, push: jest.fn(), back: jest.fn() }
  return { __router: state, useLocalSearchParams: () => state.params, useRouter: () => state }
})

jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
  useSafeAreaFrame: () => ({ x: 0, y: 0, width: 390, height: 844 }),
}))

const ana = { id: 'u2', name: 'ana' }
const said = (id: string, overrides: Partial<Post> = {}): Post => makePost(id, { parentId: 'root', author: ana, ...overrides })

function renderThread(overrides: Record<string, unknown> = {}) {
  const loadThread = jest.fn(async () => ok(makePost('root', { body: 'the post', replyCount: 1 })))
  const loadReplies = jest.fn(async (postId: string) =>
    ok(postId === 'root' ? [said('roota', { replyCount: 1 })] : [said(`${postId}a`, { parentId: postId, body: `said by ${postId}a` })]),
  )
  const reply = jest.fn(async ({ body }: { parentId: string; body: string }) => ok(said('sent', { body })))
  const toggleReaction = jest.fn(async () => ok({ emoji: '🔥', count: 7, mine: true } as Reaction))
  const useCases = {
    restoreSession: jest.fn(async () => ({ id: 'u1', name: 'me' })),
    sessionEvents: { onExpired: () => () => undefined },
    loadThread,
    loadReplies,
    reply,
    toggleReaction,
    placeNameOf: async () => 'Vigo',
    ...overrides,
  }

  let renderer!: ReturnType<typeof create>
  const tree = () => (
    <UseCasesProvider useCases={useCases as never}>
      <AuthProvider>
        <Thread />
      </AuthProvider>
    </UseCasesProvider>
  )
  act(() => {
    renderer = create(tree())
  })

  const labelled = (label: string) => renderer.root.findAll((node) => node.props.accessibilityLabel === label)
  const texts = () =>
    renderer.root
      .findAll((node) => typeof node.type === 'string' && node.children.length > 0)
      .map((node) => node.children.join(''))

  return {
    loadThread,
    loadReplies,
    reply: useCases.reply as jest.Mock,
    toggleReaction: useCases.toggleReaction as jest.Mock,
    /** Labels are set in caps by the poster type, so copy is matched without case. */
    text: (value: string) => texts().filter((t) => t.toUpperCase() === value.toUpperCase()).length,
    body: (value: string) => texts().filter((t) => t === value).length,
    has: (label: string) => labelled(label).length > 0,
    press: async (label: string) => {
      await act(async () => void labelled(label)[0]!.props.onPress())
      await flush()
    },
    /** Types into the reply bar; it says who it is on in its own label. */
    type: async (value: string) => {
      const field = renderer.root.findAll((node) => typeof node.props.placeholder === 'string' && node.props.placeholder.startsWith('Reply to'))[0]!
      await act(async () => void field.props.onChangeText(value))
    },
    barSays: (value: string) => renderer.root.findAll((node) => node.props.placeholder === value).length > 0,
  }
}

describe('the thread', () => {
  it('reads the post and what was said straight under it', async () => {
    const screen = renderThread()
    await flush()
    expect(screen.loadThread).toHaveBeenCalledWith('root')
    expect(screen.body('the post')).toBe(1)
    expect(screen.text('ana')).toBe(1)
  })

  it('says when there is no thread to read', async () => {
    const screen = renderThread({ loadThread: jest.fn(async () => err({ status: 404 })) })
    await flush()
    expect(screen.text('That post is not here any more.')).toBe(1)
  })

  it('opens one more level when asked, and closes it again', async () => {
    const screen = renderThread()
    await flush()
    await screen.press('Show 1 reply')
    expect(screen.loadReplies).toHaveBeenLastCalledWith('roota')
    expect(screen.body('said by rootaa')).toBe(1)

    await screen.press('Hide replies')
    expect(screen.body('said by rootaa')).toBe(0)
  })

  it('leaves a reaction from the post, and shows what the server counted', async () => {
    const screen = renderThread()
    await flush()
    await screen.press('Add a reaction')
    await screen.press('Fire')
    expect(screen.toggleReaction).toHaveBeenCalled()
    expect(screen.has('Fire: 7. Take it back')).toBe(true)
  })

  it('opens the picker from the plus and leaves what is picked', async () => {
    const screen = renderThread()
    await flush()
    expect(screen.has('Like')).toBe(false)
    await screen.press('Add a reaction')
    expect(screen.has('Like')).toBe(true)
    await screen.press('Like')
    expect(screen.toggleReaction).toHaveBeenCalledWith(expect.objectContaining({ id: 'root' }), '👍')
    // Picking closes the strip again.
    expect(screen.has('Like')).toBe(false)
  })

  it('puts the reply bar on whoever REPLY was pressed under', async () => {
    const screen = renderThread()
    await flush()
    expect(screen.barSays('Reply to bruno')).toBe(true)
    await screen.press('Reply to ana')
    expect(screen.barSays('Reply to ana')).toBe(true)
  })

  it('shows a reply before the server has answered, and the real one once it has', async () => {
    let settle: (result: Result<Post, { status: number }>) => void = () => undefined
    const screen = renderThread({
      reply: jest.fn(
        () =>
          new Promise<Result<Post, { status: number }>>((resolve) => {
            settle = resolve
          }),
      ),
    })
    await flush()
    await screen.type('my answer')
    await screen.press('Send')
    expect(screen.reply).toHaveBeenCalledWith({ parentId: 'root', body: 'my answer' })
    expect(screen.body('my answer')).toBe(1)

    settle(ok(said('sent', { body: 'what the server kept' })))
    await flush()
    expect(screen.body('my answer')).toBe(0)
    expect(screen.body('what the server kept')).toBe(1)
  })
})
