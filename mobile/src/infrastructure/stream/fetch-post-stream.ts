import { FEED_RADIUS_KM, type PostStream, type StreamEvent } from '../../domain'
import { STREAM_PATH } from '../http/endpoints'
import { toPost, type PostDto } from '../http/post-dto'
import { makeSseParser, type SseMessage } from './sse-parser'

/** The subset of fetch the stream needs; `expo/fetch` provides it with streaming bodies on native and web. */
export type StreamFetch = (
  url: string,
  init: { headers: Record<string, string>; signal: AbortSignal },
) => Promise<{ ok: boolean; body: { getReader: () => { read: () => Promise<{ done: boolean; value?: Uint8Array }> } } | null }>

export type FetchPostStreamDeps = {
  readonly fetch: StreamFetch
  readonly getBaseUrl: () => Promise<string>
  readonly getAccessToken: () => Promise<string | null>
  /** How far out to watch, in km; the same reach the feed reads by. */
  readonly radiusKm?: number
  readonly retryDelaysMs?: readonly number[]
  /** Replaceable for tests. */
  readonly wait?: (ms: number, signal: AbortSignal) => Promise<void>
}

const defaultWait = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => (clearTimeout(timer), resolve()), { once: true })
  })

/**
 * Reads one message of the stream; everything else on it is someone else's business.
 *
 * The server (RELY-91) says `event: post` for a post said in the locality, and nothing else; a
 * line starting with `:` is a keepalive and never reaches here as a message. `post_removed`
 * carries `{"id": …}` for a post taken down while you were reading it - RELY-99 asks for it and
 * the feed acts on it, though the stream does not say it yet. Anything else (pings, events we do
 * not know) is ignored rather than guessed at.
 */
const toStreamEvent = (message: SseMessage): StreamEvent | null => {
  try {
    if (message.event === 'post') return { kind: 'new_post', post: toPost(JSON.parse(message.data) as PostDto) }
    if (message.event !== 'post_removed') return null
    const { id } = JSON.parse(message.data) as { id?: unknown }
    return typeof id === 'string' ? { kind: 'post_removed', postId: id } : null
  } catch {
    return null
  }
}

/**
 * Reads GET /api/stream?cell=…&radius=… as Server-Sent Events over fetch (EventSource cannot send
 * the auth header and does not exist on React Native). Reconnects with backoff until unsubscribed.
 *
 * The radius goes on the query so the stream watches exactly as far out as the feed reads. The
 * token goes along when there is one, though the stream is public.
 */
export const makeFetchPostStream = ({
  fetch,
  getBaseUrl,
  getAccessToken,
  radiusKm = FEED_RADIUS_KM,
  retryDelaysMs = [1000, 2000, 5000, 15000, 30000],
  wait = defaultWait,
}: FetchPostStreamDeps): PostStream => ({
  subscribe(cell, onEvent) {
    const controller = new AbortController()
    const { signal } = controller

    async function readOnce(): Promise<boolean> {
      const token = await getAccessToken()
      const url = `${await getBaseUrl()}${STREAM_PATH}?cell=${encodeURIComponent(cell)}&radius=${radiusKm}`
      const headers: Record<string, string> = { Accept: 'text/event-stream' }
      if (token) headers.Authorization = `Bearer ${token}`
      const response = await fetch(url, { headers, signal })
      if (!response.ok || !response.body) return false
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      const parse = makeSseParser()
      for (;;) {
        const { done, value } = await reader.read()
        if (done) return true
        for (const message of parse(decoder.decode(value, { stream: true }))) {
          const event = toStreamEvent(message)
          if (event && !signal.aborted) onEvent(event)
        }
      }
    }

    void (async () => {
      let failures = 0
      while (!signal.aborted) {
        let connected = false
        try {
          connected = await readOnce()
        } catch {
          connected = false
        }
        if (signal.aborted) return
        failures = connected ? 0 : failures + 1
        await wait(retryDelaysMs[Math.min(failures, retryDelaysMs.length) - 1] ?? retryDelaysMs[0] ?? 1000, signal)
      }
    })()

    return () => controller.abort()
  },
})
