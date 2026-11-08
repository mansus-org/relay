import { makeFetchPostStream, type StreamFetch } from '../stream/fetch-post-stream'
import { makeSseParser } from '../stream/sse-parser'
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
    unsubscribe = stream.subscribe('cell/1', (post) => received.push(post.id))
    await new Promise((r) => setTimeout(r, 20))
    expect(received).toEqual(['p1'])
    expect(calls[0]).toEqual({
      url: 'https://x/api/stream?cell=cell%2F1',
      headers: { Accept: 'text/event-stream', Authorization: 'Bearer tok' },
    })
    expect(calls).toHaveLength(2)
    expect(waits.length).toBeGreaterThan(0)
  })
})
