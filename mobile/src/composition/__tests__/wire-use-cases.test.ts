import { makeFakeServer, urlOf, type FakeHandler } from '../../testing/fake-server'
import { makeFakeLocationProvider, makeFakePlaceNamer, makeMemoryStorage } from '../../testing/fakes'
import { wireUseCases } from '../wire-use-cases'

const user = { id: 'u1', name: 'Ada' }

function setup(handler: FakeHandler, secure: Record<string, string> = {}, prefs: Record<string, string> = {}) {
  const server = makeFakeServer(handler)
  const secureStorage = makeMemoryStorage(secure)
  const preferenceStorage = makeMemoryStorage(prefs)
  const useCases = wireUseCases({ secureStorage, preferenceStorage, httpAdapter: server.adapter })
  return { useCases, secureStorage, preferenceStorage, seen: server.seen }
}

describe('wired app', () => {
  it('logs in against the entered server and stores the tokens', async () => {
    const { useCases, secureStorage, seen } = setup(() => ({
      status: 200,
      data: { access_token: 'a', refresh_token: 'r', user },
    }))
    const result = await useCases.login({ serverUrl: 'https://friends.example/', username: 'ada', password: 'pw' })
    expect(result).toEqual({ ok: true, value: user })
    expect(urlOf(seen[0]!)).toBe('https://friends.example/api/auth/login')
    expect(secureStorage.data.get('access_token')).toBe('a')
    expect(secureStorage.data.get('refresh_token')).toBe('r')
  })

  it('registers with an invite token and stores the tokens', async () => {
    const { useCases, secureStorage, seen } = setup(() => ({
      status: 201,
      data: { access_token: 'a', refresh_token: 'r', user },
    }))
    const result = await useCases.register({ inviteToken: 'inv', displayName: 'Ada', username: 'ada', password: 'pw' })
    expect(result).toEqual({ ok: true, value: user })
    expect(urlOf(seen[0]!)).toBe('https://relay.mansus.org/api/auth/register')
    expect(secureStorage.data.get('access_token')).toBe('a')
  })

  it('restores the session on launch through the refresh endpoint', async () => {
    const { useCases, secureStorage } = setup(
      () => ({ status: 200, data: { access_token: 'new', refresh_token: 'r2', user } }),
      { access_token: 'old', refresh_token: 'r1' },
    )
    expect(await useCases.restoreSession()).toEqual(user)
    expect(secureStorage.data.get('access_token')).toBe('new')
  })

  it('shares one refresh between concurrent restores', async () => {
    const { useCases, seen } = setup(
      (c) => (c.url === '/auth/refresh' ? { status: 200, data: { access_token: 'new', user } } : { status: 404 }),
      { access_token: 'old', refresh_token: 'r1' },
    )
    await Promise.all([useCases.restoreSession(), useCases.restoreSession()])
    expect(seen.filter((c) => c.url === '/auth/refresh')).toHaveLength(1)
  })

  it('clears the tokens when the launch refresh is rejected, without a retry loop', async () => {
    const { useCases, secureStorage, seen } = setup(() => ({ status: 401 }), { access_token: 'old', refresh_token: 'r1' })
    const expired = jest.fn()
    useCases.sessionEvents.onExpired(expired)
    expect(await useCases.restoreSession()).toBeNull()
    expect(secureStorage.data.size).toBe(0)
    expect(seen).toHaveLength(1)
    expect(expired).not.toHaveBeenCalled() // launch restore redirects through the auth guard, not the expiry event
  })
})

describe('wired feed', () => {
  const posts = { posts: [{ id: 'p1', author: user, body: 'hi', created_at: '2026-10-29T12:00:00Z' }], next_cursor: null }

  it('resolves the device location to a cell and loads the feed for it', async () => {
    const { provider } = makeFakeLocationProvider({ granted: true })
    const server = makeFakeServer(() => ({ status: 200, data: posts }))
    const useCases = wireUseCases({
      secureStorage: makeMemoryStorage({ access_token: 't' }),
      preferenceStorage: makeMemoryStorage(),
      httpAdapter: server.adapter,
      locationProvider: provider,
      placeNamer: makeFakePlaceNamer('Pinheiros').namer,
    })
    const location = await useCases.resolveLocation({ prompt: true })
    if (!location.ok) throw new Error('location failed')
    expect(location.value.placeName).toBe('Pinheiros')
    const feed = await useCases.loadFeed({ cell: location.value.cell })
    expect(feed.ok && feed.value.posts[0]?.id).toBe('p1')
    expect(server.seen[0]!.params).toEqual({ cell: location.value.cell, radius: 10, cursor: undefined })
    expect(urlOf(server.seen[0]!)).toBe('https://relay.mansus.org/api/feed')
  })
})
