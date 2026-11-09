import { AxiosError } from 'axios'

import { makeFakeServer, urlOf, type FakeHandler } from '../../testing/fake-server'
import { makeHttpClient, type HttpClientDeps } from '../http/client'

function setup(handler: FakeHandler, overrides: Partial<HttpClientDeps> = {}) {
  const server = makeFakeServer(handler)
  const onUnauthorized = jest.fn()
  const http = makeHttpClient({
    getBaseUrl: async () => 'https://one.example',
    getAccessToken: async () => null,
    refreshAccessToken: async () => null,
    onUnauthorized,
    ...overrides,
  })
  http.defaults.adapter = server.adapter
  return { http, seen: server.seen, onUnauthorized }
}

describe('base URL', () => {
  it('reads the base URL on every request', async () => {
    let base = 'https://one.example'
    const { http, seen } = setup(() => ({ status: 200 }), { getBaseUrl: async () => base })
    await http.get('/ping')
    base = 'https://two.example'
    await http.get('/ping')
    expect(seen.map(urlOf)).toEqual(['https://one.example/ping', 'https://two.example/ping'])
  })
})

describe('Bearer token', () => {
  it('is attached when there is an access token', async () => {
    const { http, seen } = setup(() => ({ status: 200 }), { getAccessToken: async () => 'abc' })
    await http.get('/ping')
    expect(seen[0]!.headers.get('Authorization')).toBe('Bearer abc')
  })

  it('is omitted when there is none', async () => {
    const { http, seen } = setup(() => ({ status: 200 }))
    await http.get('/ping')
    expect(seen[0]!.headers.get('Authorization')).toBeFalsy()
  })
})

describe('401 handling', () => {
  // A 401 only means "session gone" when there was a session. Every test here is a signed-in one.
  const signedIn = { getAccessToken: async () => 'old' }
  const needsNew: FakeHandler = (c) =>
    c.headers.get('Authorization') === 'Bearer new' ? { status: 200, data: { ok: true } } : { status: 401 }

  it('refreshes once and retries with the new token', async () => {
    let token = 'old' // the real refresh stores the new token, which the retry then reads
    const refreshAccessToken = jest.fn(async () => (token = 'new'))
    const { http, seen } = setup(needsNew, { getAccessToken: async () => token, refreshAccessToken })
    const res = await http.get('/ping')
    expect(res.data).toEqual({ ok: true })
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(seen).toHaveLength(2)
  })

  it('calls onUnauthorized once and does not retry when the refresh fails', async () => {
    const refreshAccessToken = jest.fn(async () => null)
    const { http, seen, onUnauthorized } = setup(() => ({ status: 401 }), { ...signedIn, refreshAccessToken })
    await expect(http.get('/ping')).rejects.toBeInstanceOf(AxiosError)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(seen).toHaveLength(1)
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('treats a throwing refresh as a failed refresh', async () => {
    const { http, onUnauthorized } = setup(() => ({ status: 401 }), {
      ...signedIn,
      refreshAccessToken: async () => {
        throw new Error('boom')
      },
    })
    await expect(http.get('/ping')).rejects.toBeInstanceOf(AxiosError)
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('does not refresh a skipAuthRefresh request (login)', async () => {
    const refreshAccessToken = jest.fn(async () => 'new')
    const { http, seen, onUnauthorized } = setup(() => ({ status: 401 }), { ...signedIn, refreshAccessToken })
    await expect(http.post('/auth/login', {}, { skipAuthRefresh: true })).rejects.toBeInstanceOf(AxiosError)
    expect(refreshAccessToken).not.toHaveBeenCalled()
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(seen).toHaveLength(1)
  })

  it('does not retry a second time when the retry also gets 401', async () => {
    const refreshAccessToken = jest.fn(async () => 'new')
    const { http, seen } = setup(() => ({ status: 401 }), { ...signedIn, refreshAccessToken })
    await expect(http.get('/ping')).rejects.toBeInstanceOf(AxiosError)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(seen).toHaveLength(2)
  })

  it('passes other errors through untouched', async () => {
    const refreshAccessToken = jest.fn(async () => 'new')
    const { http } = setup(() => ({ status: 500 }), { refreshAccessToken })
    await expect(http.get('/ping')).rejects.toBeInstanceOf(AxiosError)
    expect(refreshAccessToken).not.toHaveBeenCalled()
  })

  describe('with no access token (a stranger)', () => {
    it('reports the 401 without refreshing or ending a session', async () => {
      const refreshAccessToken = jest.fn(async () => 'new')
      const { http, seen, onUnauthorized } = setup(() => ({ status: 401 }), { refreshAccessToken })
      await expect(http.get('/feed')).rejects.toBeInstanceOf(AxiosError)
      expect(refreshAccessToken).not.toHaveBeenCalled()
      expect(onUnauthorized).not.toHaveBeenCalled()
      expect(seen).toHaveLength(1)
    })
  })
})
