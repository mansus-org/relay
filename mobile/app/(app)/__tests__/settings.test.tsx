import { act, create } from 'react-test-renderer'
import type { ReactNode } from 'react'
import { TextInput } from 'react-native'

import type { UseCases } from '../../../src/application'
import { err, ok, type NodeError, type NodeTest, type Profile, type Result } from '../../../src/domain'
import { AuthProvider, useAuth } from '../../../src/presentation/auth'
import { Button } from '../../../src/presentation/components/Button'
import { DisplayNameSheet } from '../../../src/presentation/components/DisplayNameSheet'
import { NodeSheet } from '../../../src/presentation/components/NodeSheet'
import { SignOutSheet } from '../../../src/presentation/components/SignOutSheet'
import { UseCasesProvider } from '../../../src/presentation/use-cases'

import Settings from '../settings'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = (ms = 60) => act(async () => void (await new Promise((r) => setTimeout(r, ms))))

jest.mock('expo-router', () => {
  const { Text } = jest.requireActual('react-native')
  const state = {
    params: {},
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    canGoBack: () => false,
    setParams: jest.fn(),
  }
  return {
    __router: state,
    Link: ({ children }: { children: ReactNode }) => <Text>{children}</Text>,
    useFocusEffect: () => undefined,
    useLocalSearchParams: () => ({}),
    usePathname: () => '/settings',
    useRouter: () => state,
  }
})

const router = (
  jest.requireMock('expo-router') as { __router: { push: jest.Mock; replace: jest.Mock; back: jest.Mock } }
).__router

jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useSafeAreaInsets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
  useSafeAreaFrame: () => ({ x: 0, y: 0, width: 390, height: 844 }),
}))

jest.mock('expo-constants', () => ({ expoConfig: { version: '2.0.0' } }))

const ada: Profile = { handle: 'ada', displayName: 'Ada L.', isAdmin: false }
const answered = (host: string, reachable = true): NodeTest => ({
  host,
  reachable,
  version: reachable ? '0.3.1' : null,
  reason: reachable ? null : 'no answer from that server',
})

/** The session is not drawn on this screen, so the test reads it through a window of its own. */
function makeSessionWindow() {
  const seen: { name?: string } = {}
  const Window = () => {
    seen.name = useAuth().user?.name
    return null
  }
  return { seen, Window }
}

function renderSettings(
  {
    profile = ada,
    serverUrl = 'https://relay.mansus.org',
    answer,
    moved = ok('https://other.node'),
  }: {
    profile?: Profile | null
    serverUrl?: string
    answer?: (url: string) => NodeTest
    moved?: Result<string, NodeError>
  } = {},
) {
  const hostOf = (url: string) => url.replace(/^https?:\/\//, '').split('/')[0]!
  const getProfile = jest.fn(async () => (profile ? ok(profile) : err('no-session')))
  const readServerUrl = jest.fn(async () => serverUrl)
  const updateProfile = jest.fn(async (displayName: string) => ok({ ...profile, displayName }))
  const testNode = jest.fn(async (url: string) => ok(answer ? answer(url) : answered(hostOf(url))))
  const switchNode = jest.fn(async () => moved)
  const logout = jest.fn(async () => undefined)
  const { seen, Window } = makeSessionWindow()

  const useCases = {
    restoreSession: async () => ({ id: '1', name: profile?.displayName ?? 'Ada L.' }),
    sessionEvents: { onExpired: () => () => undefined },
    login: jest.fn(),
    register: jest.fn(),
    logout,
    getProfile,
    readServerUrl,
    updateProfile,
    testNode,
    switchNode,
  } as unknown as UseCases

  const tree = () => (
    <UseCasesProvider useCases={useCases}>
      <AuthProvider>
        <Settings />
        <Window />
      </AuthProvider>
    </UseCasesProvider>
  )

  let renderer!: ReturnType<typeof create>
  act(() => {
    renderer = create(tree())
  })

  const texts = () =>
    renderer.root
      .findAll((node) => typeof node.type === 'string' && node.children.length > 0)
      .map((node) => node.children.join(''))

  // Anything the test reaches for has to be there, or the test says what is missing.
  const one = <T,>(found: T[], what: string): T => {
    const hit = found[0]
    if (!hit) throw new Error(`no ${what} on the screen`)
    return hit
  }
  const sheet = (type: unknown) => one(renderer.root.findAll((node) => node.type === type), 'sheet')
  const field = (type: unknown) => one(sheet(type).findAll((node) => node.type === TextInput), 'field')
  const button = (type: unknown, label: string) =>
    one(
      sheet(type).findAll((node) => node.type === Button && String(node.props.label).startsWith(label)),
      `button that says ${label}`,
    )

  return {
    updateProfile,
    testNode,
    switchNode,
    logout,
    /** The name the session carries, which is what the rest of the app reads back. */
    sessionName: () => seen.name,
    text: (value: string) => texts().filter((t) => t.toUpperCase() === value.toUpperCase()).length,
    open: (title: string) => {
      const row = one(
        renderer.root.findAll((node) => node.props.title === title && typeof node.props.onPress === 'function'),
        `row called ${title}`,
      )
      act(() => row.props.onPress())
    },
    isOpen: (type: unknown) => Boolean(sheet(type).props.visible),
    type: (type: unknown, value: string) => {
      act(() => field(type).props.onChangeText(value))
    },
    /** Buttons answer for their own sheet, and say whether they would let you through. */
    press: (type: unknown, label: string) => {
      act(() => button(type, label).props.onPress())
    },
    blocked: (type: unknown, label: string) => Boolean(button(type, label).props.disabled),
  }
}

describe('the settings screen', () => {
  beforeEach(() => {
    router.replace.mockClear()
    router.back.mockClear()
  })

  it('reads the account and the node it stands on', async () => {
    const screen = renderSettings()
    await flush()

    expect(screen.text('Ada L.')).toBe(1)
    expect(screen.text('@ada')).toBe(1)
    expect(screen.text('ada · relay.mansus.org')).toBe(1)
    // Nothing is open until a row is tapped.
    expect(screen.isOpen(NodeSheet)).toBe(false)
    expect(screen.isOpen(SignOutSheet)).toBe(false)
  })

  it('says so when there is no account to read', async () => {
    const screen = renderSettings({ profile: null })
    await flush()

    expect(screen.text('not signed in')).toBe(1)
    expect(screen.text('Edit')).toBe(0)
  })

  it('will not save a node until it has answered, and says which one did', async () => {
    const screen = renderSettings()
    await flush()

    screen.open('Server')
    screen.type(NodeSheet, 'https://other.node')
    expect(screen.blocked(NodeSheet, 'Save')).toBe(true)

    screen.press(NodeSheet, 'Test connection')
    await flush()

    expect(screen.testNode).toHaveBeenCalledWith('https://other.node')
    expect(screen.text('Connected to other.node · 0.3.1')).toBe(1)
    expect(screen.blocked(NodeSheet, 'Save')).toBe(false)
  })

  it('retires the answer the moment the address changes again', async () => {
    const screen = renderSettings()
    await flush()

    screen.open('Server')
    screen.press(NodeSheet, 'Test connection')
    await flush()
    // The node you already stand on answers, and there is nothing to save.
    expect(screen.text('Connected to relay.mansus.org · 0.3.1')).toBe(1)
    expect(screen.blocked(NodeSheet, 'Save')).toBe(true)

    screen.type(NodeSheet, 'https://other.node')
    expect(screen.text('Connected to other.node · 0.3.1')).toBe(0)
    expect(screen.blocked(NodeSheet, 'Save')).toBe(true)
  })

  it('refuses a node that will not answer, and keeps the one you have', async () => {
    const screen = renderSettings({ answer: () => answered('nowhere.node', false) })
    await flush()

    screen.open('Server')
    screen.type(NodeSheet, 'https://nowhere.node')
    screen.press(NodeSheet, 'Test connection')
    await flush()

    expect(screen.text('nowhere.node: no answer from that server')).toBe(1)
    expect(screen.blocked(NodeSheet, 'Save')).toBe(true)
    expect(screen.logout).not.toHaveBeenCalled()
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('moves to the node that answered, and lands on the sign-in screen', async () => {
    const screen = renderSettings()
    await flush()

    screen.open('Server')
    screen.type(NodeSheet, 'https://other.node')
    screen.press(NodeSheet, 'Test connection')
    await flush()
    screen.press(NodeSheet, 'Save')
    await flush()

    expect(screen.switchNode).toHaveBeenCalledWith('https://other.node')
    // The old token means nothing at the new place, so the session goes with the move.
    expect(screen.logout).toHaveBeenCalledTimes(1)
    expect(router.replace).toHaveBeenCalledWith('/login')
    // The row has already taken the new address, for the frame before this screen goes away.
    expect(screen.text('other.node')).toBe(1)
  })

  it('keeps the node you have when the new one dies between the test and the save', async () => {
    const screen = renderSettings({ moved: err('unreachable') })
    await flush()

    screen.open('Server')
    screen.type(NodeSheet, 'https://other.node')
    screen.press(NodeSheet, 'Test connection')
    await flush()
    screen.press(NodeSheet, 'Save')
    await flush()

    expect(screen.logout).not.toHaveBeenCalled()
    expect(router.replace).not.toHaveBeenCalled()
    expect(screen.text('That server did not answer. Nothing was changed.')).toBe(1)
    expect(screen.text('relay.mansus.org')).toBe(1)
  })

  it('keeps the name the node wrote back, and tells the session about it', async () => {
    const screen = renderSettings()
    await flush()

    screen.open('Ada L.')
    expect(screen.isOpen(DisplayNameSheet)).toBe(true)
    // The handle is not up for grabs, and the sheet says so where you are about to ask.
    expect(screen.text('Your handle stays @ada.')).toBe(1)
    expect(screen.blocked(DisplayNameSheet, 'Save')).toBe(true)

    screen.type(DisplayNameSheet, 'Ada Lovelace')
    expect(screen.blocked(DisplayNameSheet, 'Save')).toBe(false)
    screen.press(DisplayNameSheet, 'Save')
    await flush()

    expect(screen.updateProfile).toHaveBeenCalledWith('Ada Lovelace')
    expect(screen.text('Ada Lovelace')).toBe(1)
    expect(screen.sessionName()).toBe('Ada Lovelace')
  })

  it('signs out of this node and leaves nothing to read behind', async () => {
    const screen = renderSettings()
    await flush()

    screen.open('Sign out')
    expect(screen.isOpen(SignOutSheet)).toBe(true)
    screen.press(SignOutSheet, 'Sign out')
    await flush()

    expect(screen.logout).toHaveBeenCalledTimes(1)
    expect(router.replace).toHaveBeenCalledWith('/login')
  })
})
