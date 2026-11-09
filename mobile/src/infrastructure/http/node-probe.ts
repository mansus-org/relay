import { normalizeServerUrl, serverHost, type NodeProbe, type NodeTest } from '../../domain'

/**
 * The health call sits at the root of the node, not under /api, so a bare address typed into
 * settings is enough to answer it. No token: whether a place exists is not private.
 */
const HEALTH_PATH = 'health'

/** The subset of fetch a health call needs. `expo/fetch` and `globalThis.fetch` both provide it. */
export type ProbeFetch = (url: string, init: { signal: AbortSignal }) => Promise<{ status: number; json: () => Promise<unknown> }>

export type NodeProbeDeps = {
  readonly fetch?: ProbeFetch
  /** How long to wait for a node that is not answering before saying so. */
  readonly timeoutMs?: number
}

/** Only a body that looks like Relay's own answer counts as Relay answering. */
const versionOfHealth = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  const health = body as { status?: unknown; version?: unknown }
  if (typeof health.status !== 'string') return null
  return typeof health.version === 'string' ? health.version : null
}

/** Something answered, and it was not Relay. */
const notRelay = (host: string): NodeTest => ({
  host,
  reachable: false,
  version: null,
  reason: 'that is not a Relay server',
})

const unreachable = (host: string, error: unknown): NodeTest => ({
  host,
  reachable: false,
  version: null,
  reason: error instanceof Error && /abort|timeout/i.test(`${error.name} ${error.message}`) ? 'took too long to answer' : 'no answer from that server',
})

/**
 * Asks one node whether it is Relay, by calling its health endpoint without a token.
 * Never throws: whatever went wrong comes back in the answer, because the interface has to say it.
 */
export const makeHttpNodeProbe = ({ fetch = globalThis.fetch, timeoutMs = 6000 }: NodeProbeDeps = {}): NodeProbe => ({
  async check(url) {
    const host = serverHost(url)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(`${normalizeServerUrl(url)}/${HEALTH_PATH}`, { signal: controller.signal })
      if (response.status >= 400) return notRelay(host)
      const version = versionOfHealth(await response.json().catch(() => null))
      return version === null ? notRelay(host) : { host, reachable: true, version, reason: null }
    } catch (error) {
      return unreachable(host, error)
    } finally {
      clearTimeout(timer)
    }
  },
})
