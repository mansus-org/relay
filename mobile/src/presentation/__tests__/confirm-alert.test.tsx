import { TextInput } from 'react-native'
import { act, create, type ReactTestRenderer } from 'react-test-renderer'

import { ConfirmAlert } from '../components/ConfirmAlert'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Reason = { label: string; value: string; onChange: (text: string) => void; required?: boolean }

/**
 * The red button is the only thing on this modal that changes anything, so the interesting question
 * about it is when it will answer to a press. A removal the node is going to refuse for want of a
 * reason should not look pressable right up until it is pressed.
 */
function open(reason?: Reason, busy = false, error?: string) {
  let renderer!: ReactTestRenderer
  act(() => {
    renderer = create(
      <ConfirmAlert
        visible
        stamp="Not deletion"
        title="Switch off lina?"
        message="They cannot sign in any more."
        confirm="Switch off"
        reason={reason}
        error={error}
        busy={busy}
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    )
  })
  const button = renderer.root
    .findAll((node) => node.props.accessibilityRole === 'button')
    .find((node) => node.props.accessibilityLabel === 'Switch off')
  if (!button) throw new Error('the confirm button is not on the modal')
  const said = (words: string) => JSON.stringify(renderer.toJSON()).includes(words)
  const field = (props: object) =>
    renderer.root.findAll(
      (node) => node.type === TextInput && Object.entries(props).every(([key, value]) => node.props[key] === value),
    )
  return { button, said, field, unmount: () => act(() => renderer.unmount()) }
}

describe('ConfirmAlert', () => {
  it('will not let a removal through without the reason the node asks for', () => {
    const { button, unmount } = open({ label: 'Why', value: '   ', onChange: () => undefined, required: true })
    expect(button.props.disabled).toBe(true)
    unmount()
  })

  it('lets it through once something is written', () => {
    const { button, unmount } = open({ label: 'Why', value: 'repeated spam', onChange: () => undefined, required: true })
    expect(button.props.disabled).toBe(false)
    unmount()
  })

  it('does not hold a decision that needs no reason hostage', () => {
    const { button, unmount } = open()
    expect(button.props.disabled).toBe(false)
    unmount()
  })

  it('goes quiet while the node is still answering', () => {
    const { button, unmount } = open(undefined, true)
    expect(button.props.disabled).toBe(true)
    expect(button.props.accessibilityState).toEqual({ busy: true })
    unmount()
  })

  it('says why the last attempt failed, where the admin is still looking', () => {
    // The modal covers the page, so an error left on the page is an error nobody reads and the
    // button just goes back to waiting for no stated reason.
    const { said, unmount } = open(undefined, false, 'Somebody got there first. Pull to see the queue again.')
    expect(said('Somebody got there first')).toBe(true)
    unmount()
  })

  it('says nothing about a failure when nothing failed', () => {
    const { said, unmount } = open()
    expect(said('got there first')).toBe(false)
    unmount()
  })

  it('cuts the reason off where the node will read it back', () => {
    // Five hundred is the node's own limit; past it the reason is refused, and the decision with it.
    const { field, unmount } = open({ label: 'Why', value: 'repeated spam', onChange: () => undefined, required: true })
    expect(field({ maxLength: 500 })).toHaveLength(1)
    unmount()
  })
})
