import { makeFetchPostStream, type StreamFetch } from '../stream/fetch-post-stream'
import { makeSseParser } from '../stream/sse-parser'
import type { StreamEvent } from '../../domain'
import { makePostDto } from '../../testing/fakes'

describe('SSE parser', () => {
  it('parses events split across chunks, comments and CRLF', () => {
    const parse = makeSseParser()
    expect(parse(': hi\n\nevent: post\ndata: {"a"')).toEqual([])
    expect(parse(':1}\r\n\r\ndata: x\n\n')).toEqual([
      { event: 'post', data: '{"a":1}' },
      { event: 'message', data: 'x' },
    ])
  })

  it('joins multi-line data', () => {
    expect(makeSseParser()('data: a\ndata: b\n\n')).toEqual([{ event: 'message', data: 'a\nb' }])
  })
})

const encode = (text: string) => new TextEncoder().encode(text)

/** What the tests assert on: the id of whichever post the stream just reported. */
const label = (event: StreamEvent) => (event.kind === 'new_post' ? event.post.id : event.postId)

const streamOf = (chunks: string[]) => {
  const queue = chunks.map(encode)
  return {
    ok: true,
    body: { getReader: () => ({ read: async () => (queue.length ? { done: false, value: queue.shift() } : { done: true }) }) },
  }
}

describe('fetch post stream', () => {
  it('delivers posts with auth header, then reconnects until unsubscribed', async () => {
    const calls: { url: string; headers: Record<string, string> }[] = []
    let unsubscribe = () => {}
    const received: string[] = []
    const fetch: StreamFetch = async (url, init) => {
      calls.push({ url, headers: init.headers })
      if (calls.length === 1) {
        return streamOf([`event: post\ndata: ${JSON.stringify(makePostDto('p1'))}\n\n`, 'event: ping\ndata: 1\n\n', 'event: post\ndata: not json\n\n'])
      }
      unsubscribe()
      return { ok: false, body: null }
    }
    const waits: number[] = []
    const stream = makeFetchPostStream({
      fetch,
      getBaseUrl: async () => 'https://x/api',
      getAccessToken: async () => 'tok',
      wait: async (ms) => void waits.push(ms),
    })
    unsubscribe = stream.subscribe('cell/1', (event) => received.push(label(event)))
    await new Promise((r) => setTimeout(r, 20))
    expect(received).toEqual(['p1'])
    expect(calls[0]).toEqual({
      url: 'https://x/api/stream?cell=cell%2F1&radius=10',
      headers: { Accept: 'text/event-stream', Authorization: 'Bearer tok' },
    })
    expect(calls).toHaveLength(2)
    expect(waits.length).toBeGreaterThan(0)
  })

  it('reports a removal and a new post, and ignores pings, names it does not know and bodies it cannot read', async () => {
    let calls = 0
    let unsubscribe = () => {}
    const received: string[] = []
    const fetch: StreamFetch = async () => {
      calls += 1
      if (calls === 1) {
        return streamOf([
          `event: post_removed\ndata: ${JSON.stringify({ id: 'p9' })}\n\n`,
          `event: post\ndata: ${JSON.stringify(makePostDto('p3'))}\n\n`,
          'event: ping\ndata: 1\n\n',
          `event: new_post\ndata: ${JSON.stringify(makePostDto('p4'))}\n\n`,
          'event: post\ndata: not json\n\n',
        ])
      }
      unsubscribe()
      return { ok: false, body: null }
    }
    const stream = makeFetchPostStream({
      fetch,
      getBaseUrl: async () => 'https://x/api',
      getAccessToken: async () => 'tok',
      wait: async () => {},
    })
    unsubscribe = stream.subscribe('cell/1', (event) => received.push(label(event)))
    await new Promise((r) => setTimeout(r, 20))
    expect(received).toEqual(['p9', 'p3'])
  })

  it('waits longer after each failed connection, up to half a minute', async () => {
    const waits: number[] = []
    let unsubscribe = () => {}
    const stream = makeFetchPostStream({
      fetch: async () => ({ ok: false, body: null }),
      getBaseUrl: async () => 'https://x/api',
      getAccessToken: async () => 'tok',
      wait: async (ms) => {
        waits.push(ms)
        if (waits.length === 6) unsubscribe()
      },
    })
    unsubscribe = stream.subscribe('cell-1', () => {})
    await new Promise((r) => setTimeout(r, 20))
    expect(waits).toEqual([1000, 2000, 5000, 15000, 30000, 30000])
  })
})
