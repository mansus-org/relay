import { act, create } from 'react-test-renderer'
import { Platform } from 'react-native'
import type { ReactNode } from 'react'

import { makeReadPostalCode, makeResolvePostalCode, type UseCases } from '../../../src/application'
import { err, ok, type FeedPage, type Post } from '../../../src/domain'
import { AuthProvider } from '../../../src/presentation/auth'
import { UseCasesProvider } from '../../../src/presentation/use-cases'
import { makeFakePostalCodeResolver, makePostalArea, makePost } from '../../../src/testing/fakes'

import Feed from '../index'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = (ms = 100) => act(async () => void (await new Promise((r) => setTimeout(r, ms))))

// The feed screen is a router screen: it reads the place off the query and writes it back to the
// address bar, so the router is mocked here and both directions are observable.
type MockRouter = { params: Record<string, string>; push: jest.Mock; setParams: jest.Mock }

jest.mock('expo-router', () => {
  const { Text } = jest.requireActual('react-native')
  const state = { params: {} as Record<string, string>, push: jest.fn(), setParams: jest.fn() }
  return {
    __router: state,
    Link: ({ children }: { children: ReactNode }) => <Text>{children}</Text>,
    useFocusEffect: () => undefined,
    useLocalSearchParams: () => state.params,
    useRouter: () => state,
  }
})

const router = (jest.requireMock('expo-router') as { __router: MockRouter }).__router

jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
  useSafeAreaFrame: () => ({ x: 0, y: 0, width: 390, height: 844 }),
}))

const platform = Platform as unknown as { OS: string }
const native = platform.OS

function renderFeed(
  posts: Post[],
  { saved = '15003', params = {}, located = false }: { saved?: string | null; params?: Record<string, string>; located?: boolean } = {},
) {
  const resolver = makeFakePostalCodeResolver({
    '15003': makePostalArea('15003', 'A Coruña', 'cell-coruna'),
    '36201': makePostalArea('36201', 'Vigo', 'cell-vigo'),
  })
  const store = { read: async () => saved, save: async () => undefined }
  const loadFeed = jest.fn(async () => ok<FeedPage>({ posts, nextCursor: null }))
  const useCases = {
    // Nothing to restore: whoever this is, they have no session.
    restoreSession: jest.fn(async () => null),
    sessionEvents: { onExpired: () => () => undefined },
    // The browser is asked first; it usually has no answer here, which is what the postal code is for.
    resolveLocation: async () =>
      located ? ok({ cell: 'cell-gps', placeName: null }) : err({ kind: 'denied' as const, canAskAgain: false }),
    resolvePostalCode: makeResolvePostalCode({ resolver, store }),
    readPostalCode: makeReadPostalCode({ store }),
    loadFeed,
    placeNameOf: async () => 'A Coruña',
    subscribeToPosts: () => () => undefined,
  } as unknown as UseCases

  router.params = params
  let renderer!: ReturnType<typeof create>
  const tree = () => (
    <UseCasesProvider useCases={useCases}>
      <AuthProvider>
        <Feed />
      </AuthProvider>
    </UseCasesProvider>
  )
  act(() => {
    renderer = create(tree())
  })
  const texts = () =>
    renderer.root
      .findAll((node) => typeof node.type === 'string' && node.children.length > 0)
      .map((node) => node.children.join(''))

  return {
    loadFeed,
    /** Rerender with a new query, the way a router navigation would. */
    navigate: async (next: Record<string, string>) => {
      router.params = next
      await act(async () => {
        renderer.update(tree())
        await Promise.resolve()
      })
      return flush()
    },
    /** Labels are set in caps by the poster type, so copy is matched without case. */
    text: (value: string) => texts().filter((t) => t.toUpperCase() === value.toUpperCase()).length,
    labelled: (label: string) => renderer.root.findAll((node) => node.props.accessibilityLabel === label).length,
  }
}

describe('the feed with no session', () => {
  beforeAll(() => void (platform.OS = 'web'))
  afterAll(() => void (platform.OS = native))
  beforeEach(() => {
    router.push.mockClear()
    router.setParams.mockClear()
  })

  it('reads the feed, and offers Sign in instead of anything that writes', async () => {
    const screen = renderFeed([makePost('a'), makePost('b')])
    await flush()

    expect(screen.text('post a')).toBe(1)
    expect(screen.text('post b')).toBe(1)
    expect(screen.text('Sign in')).toBe(1)
    // No publish button, no communities, and the place is still theirs to change.
    expect(screen.labelled('New post')).toBe(0)
    expect(screen.labelled('Communities')).toBe(0)
    expect(screen.text('Change')).toBe(1)
    // Nobody bounced them to /login for want of a session.
    expect(router.push).not.toHaveBeenCalled()
  })

  it('answers an empty place with Sign in, not with Be the first to post', async () => {
    const screen = renderFeed([])
    await flush()

    expect(screen.text('Nothing nearby yet.')).toBe(1)
    expect(screen.text('Be the first to post.')).toBe(0)
    // Once in the header, once in the empty state.
    expect(screen.text('Sign in')).toBe(2)
  })

  it('opens the place the address names, and leaves it in the address bar', async () => {
    const screen = renderFeed([makePost('a')], { saved: '36201', params: { code: '15003' } })
    await flush()

    expect(screen.loadFeed).toHaveBeenCalledWith({ cell: 'cell-coruna', cursor: undefined })
    expect(router.setParams).toHaveBeenCalledWith({ code: '15003' })
  })

  it('keeps the place a reader chose over the one still in the address', async () => {
    const screen = renderFeed([makePost('a')], { saved: '36201' })
    await flush()
    expect(screen.loadFeed).toHaveBeenCalledWith({ cell: 'cell-vigo', cursor: undefined })

    // The address they arrived on is still on screen; it must not pull them back mid-read.
    await screen.navigate({ code: '15003' })
    expect(screen.loadFeed).toHaveBeenCalledTimes(1)
    expect(screen.loadFeed).toHaveBeenCalledWith({ cell: 'cell-vigo', cursor: undefined })
  })

  it('opens on where the browser says it is, not on the code it remembers', async () => {
    const screen = renderFeed([makePost('a')], { saved: '15003', located: true })
    await flush()
    expect(screen.loadFeed).toHaveBeenCalledWith({ cell: 'cell-gps', cursor: undefined })
    expect(screen.text('Sign in')).toBe(1)
  })

  it('offers to ask the browser again, but only when this browser can be asked', async () => {
    const navigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
    Object.defineProperty(globalThis, 'navigator', { value: { geolocation: {} }, configurable: true })
    const asked = renderFeed([], { saved: null })
    await flush()
    expect(asked.text('Use my location')).toBe(1)

    // Over plain http the API is never handed out, so the offer would be a dead end.
    if (navigator) Object.defineProperty(globalThis, 'navigator', navigator)
    const plain = renderFeed([], { saved: null })
    await flush()
    expect(plain.text('Use my location')).toBe(0)
    expect(plain.text('Show me nearby')).toBe(1)
  })
})
