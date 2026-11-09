/** Why moving to a node was refused before anything was written. */
export type NodeError = 'bad-url' | 'unreachable'

/** What one round trip to a node found out. */
export type NodeTest = {
  readonly host: string
  /** The node answered the health call. */
  readonly reachable: boolean
  /** The version it reported, when it reported one. */
  readonly version: string | null
  /** Why it did not answer, in one short phrase, when it did not. */
  readonly reason: string | null
}

/**
 * The one sentence the interface says after a test, so the wording never drifts per screen.
 *
 * A node that answers is a fact about the place you now live. A node that does not is still
 * your address: the app did not change it, and saying so is the whole point of the sentence.
 */
export const describeNodeTest = (test: NodeTest): string => {
  if (test.reachable) return `Connected to ${test.host}${test.version ? ` · ${test.version}` : ''}`
  return `${test.host}: ${test.reason ?? 'no answer from that server'}`
}
