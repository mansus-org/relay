import { SafeAreaProvider } from 'react-native-safe-area-context'
import { act, create, type ReactTestRenderer } from 'react-test-renderer'

import type { AdminMember, MemberDetail } from '../../../domain'
import { MemberSheet } from '../MemberSheet'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const screen = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 59, left: 0, right: 0, bottom: 34 } }

const member = (overrides: Partial<AdminMember> = {}): AdminMember => ({
  id: 4,
  name: 'Lina Ferrer',
  handle: 'lina',
  joinedAt: '2025-03-12T10:00:00',
  isAdmin: false,
  deactivatedAt: null,
  ...overrides,
})

/**
 * The sheet is the only place an account can be switched off, and the node refuses three kinds of
 * hand reaching for that switch: your own, another admin's, and one already thrown. What is on
 * screen has to say which of those it is, instead of offering a button that only answers 403.
 */
function open(account: AdminMember, myHandle = 'ada') {
  const onRemove = jest.fn()
  const detail: MemberDetail = { member: account, history: [] }
  let renderer!: ReactTestRenderer
  act(() => {
    renderer = create(
      <SafeAreaProvider initialMetrics={screen}>
        <MemberSheet detail={detail} myHandle={myHandle} removing={false} onClose={() => undefined} onRemove={onRemove} />
      </SafeAreaProvider>,
    )
  })
  const theSwitch = () =>
    renderer.root
      .findAll((node) => node.props.accessibilityRole === 'button')
      .find((node) => node.props.accessibilityLabel === 'Switch off')
  const said = (words: string) => JSON.stringify(renderer.toJSON()).includes(words)
  return { theSwitch, said, onRemove }
}

describe('MemberSheet', () => {
  it('offers the switch for an account that is on, and not yours', () => {
    expect(open(member()).theSwitch()).toBeTruthy()
  })

  it('will not offer to switch off the account you are reading this from', () => {
    expect(open(member({ handle: 'ada' }), 'ada').theSwitch()).toBeUndefined()
  })

  it('will not offer it for another admin either, and says why', () => {
    const t = open(member({ handle: 'theo', isAdmin: true }))
    expect(t.theSwitch()).toBeUndefined()
    expect(t.said('Admins cannot be switched off from here.')).toBe(true)
  })

  it('does not offer to switch off an account that is already off', () => {
    // There is no way back on the node yet, so the sheet states the state and stops there.
    const t = open(member({ deactivatedAt: '2025-04-01T09:00:00' }))
    expect(t.theSwitch()).toBeUndefined()
    expect(t.said('This account is already switched off.')).toBe(true)
  })
})
