import { makeHttpClient } from '../http/client'
import { makeHttpCommunityRepository, makeHttpFeedRepository, makeHttpPostRepository } from '../http/feed-repository'
import { makeFakeServer, type FakeHandler } from '../../testing/fake-server'
import { makePostDto } from '../../testing/fakes'

function setup(handler: FakeHandler) {
  const server = makeFakeServer(handler)
  const http = makeHttpClient({
    getBaseUrl: async () => 'https://x/api',
    getAccessToken: async () => 't',
    refreshAccessToken: async () => null,
    onUnauthorized: () => {},
  })
  http.defaults.adapter = server.adapter
  return { http, seen: server.seen }
}

describe('feed repository', () => {
  it('requests the feed with cell, radius and cursor and maps the page', async () => {
    const { http, seen } = setup(() => ({ status: 200, data: { posts: [makePostDto('p1')], next_cursor: 'c2' } }))
    const result = await makeHttpFeedRepository({ http }).list({ cell: 'abc', radiusKm: 10, cursor: 'c1' })
    expect(seen[0]!.params).toEqual({ cell: 'abc', radius: 10, cursor: 'c1' })
    expect(result).toEqual({
      ok: true,
      value: {
        nextCursor: 'c2',
        posts: [
          {
            id: 'p1',
            author: { id: 'u1', name: 'bruno' },
            body: 'post p1',
            createdAt: '2026-10-29T12:00:00Z',
            locationCell: '88a8100d6dfffff',
            reactions: [{ emoji: '🔥', count: 4, mine: true }],
            replyCount: 3,
          },
        ],
      },
    })
  })

  it('treats a missing next_cursor as the last page', async () => {
    const { http } = setup(() => ({ status: 200, data: { posts: [] } }))
    const result = await makeHttpFeedRepository({ http }).list({ cell: 'abc', radiusKm: 10 })
    expect(result).toEqual({ ok: true, value: { posts: [], nextCursor: null } })
  })

  it('maps failures', async () => {
    const { http } = setup(() => ({ status: 500 }))
    expect(await makeHttpFeedRepository({ http }).list({ cell: 'abc', radiusKm: 10 })).toEqual({ ok: false, error: 'unexpected' })
  })
})

describe('post repository', () => {
  it('posts location_cell and community_id when set', async () => {
    const { http, seen } = setup(() => ({ status: 201, data: makePostDto('n') }))
    const result = await makeHttpPostRepository({ http }).create({ body: 'hi', locationCell: 'abc', communityId: 'c1' })
    expect(result.ok).toBe(true)
    expect(seen[0]!.url).toBe('/posts')
    expect(JSON.parse(seen[0]!.data as string)).toEqual({ body: 'hi', location_cell: 'abc', community_id: 'c1' })
  })

  it('omits location_cell and community_id when not set', async () => {
    const { http, seen } = setup(() => ({ status: 201, data: makePostDto('n', { location_cell: null }) }))
    await makeHttpPostRepository({ http }).create({ body: 'hi' })
    expect(JSON.parse(seen[0]!.data as string)).toEqual({ body: 'hi' })
  })
})

describe('community repository', () => {
  it('lists joined communities', async () => {
    const { http } = setup(() => ({ status: 200, data: { communities: [{ id: '1', name: 'Vizinhos', extra: 1 }] } }))
    expect(await makeHttpCommunityRepository({ http }).listJoined()).toEqual({ ok: true, value: [{ id: '1', name: 'Vizinhos' }] })
  })

  it('returns no communities while the endpoint is missing', async () => {
    const { http } = setup(() => ({ status: 404 }))
    expect(await makeHttpCommunityRepository({ http }).listJoined()).toEqual({ ok: true, value: [] })
  })
})
