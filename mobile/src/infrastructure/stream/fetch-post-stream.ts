import type { Post, PostStream } from '../../domain'
import { STREAM_PATH } from '../http/endpoints'
import { toPost, type PostDto } from '../http/post-dto'
import { makeSseParser } from './sse-parser'

/** The subset of fetch the stream needs; `expo/fetch` provides it with streaming bodies on native and web. */
export type StreamFetch = (
  url: string,
  init: { headers: Record<string, string>; signal: AbortSignal },
) => Promise<{ ok: boolean; body: { getReader: () => { read: () => Promise<{ done: boolean; value?: Uint8Array }> } } | null }>

export type FetchPostStreamDeps = {
  readonly fetch: StreamFetch
  readonly getBaseUrl: () => Promise<string>
  readonly getAccessToken: () => Promise<string | null>
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
 * Reads GET /stream?cell=… as Server-Sent Events over fetch (EventSource cannot send the auth
 * header and does not exist on React Native). Reconnects with backoff until unsubscribed.
 * Assumed event: `event: post` with the post JSON as data.
 */
export const makeFetchPostStream = ({
  fetch,
  getBaseUrl,
  getAccessToken,
  retryDelaysMs = [1000, 2000, 5000, 15000, 30000],
  wait = defaultWait,
}: FetchPostStreamDeps): PostStream => ({
  subscribe(cell, onPost) {
    const controller = new AbortController()
    const { signal } = controller

    async function readOnce(): Promise<boolean> {
      const token = await getAccessToken()
      const url = `${await getBaseUrl()}${STREAM_PATH}?cell=${encodeURIComponent(cell)}`
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
          if (message.event !== 'post') continue
          let post: Post
          try {
            post = toPost(JSON.parse(message.data) as PostDto)
          } catch {
            continue
          }
          if (!signal.aborted) onPost(post)
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
