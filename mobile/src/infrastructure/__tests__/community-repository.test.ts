import { makeHttpClient } from '../http/client'
import { makeHttpCommunityRepository } from '../http/community-repository'
import { makeFakeServer, type FakeHandler } from '../../testing/fake-server'
import { makeCommunityDto, makePostDto } from '../../testing/fakes'

function setup(handler: FakeHandler) {
  const server = makeFakeServer(handler)
  const http = makeHttpClient({
    getBaseUrl: async () => 'https://x/api',
    getAccessToken: async () => 't',
    refreshAccessToken: async () => null,
    onUnauthorized: () => {},
  })
  http.defaults.adapter = server.adapter
  return { repository: makeHttpCommunityRepository({ http }), seen: server.seen }
}

describe('community repository', () => {
  it('lists joined communities', async () => {
    const { repository } = setup(() => ({ status: 200, data: { communities: [{ id: '1', name: 'Vizinhos', extra: 1 }] } }))
    expect(await repository.listJoined()).toEqual({ ok: true, value: [{ id: '1', name: 'Vizinhos' }] })
  })

  it('returns no joined communities while the endpoint is missing', async () => {
    const { repository } = setup(() => ({ status: 404 }))
    expect(await repository.listJoined()).toEqual({ ok: true, value: [] })
  })

  it('lists nearby communities for a cell, from a bare array or an envelope', async () => {
    const bare = setup(() => ({ status: 200, data: [makeCommunityDto('c1')] }))
    const result = await bare.repository.listNearby('abc')
    expect(bare.seen[0]!.url).toBe('/communities')
    expect(bare.seen[0]!.params).toEqual({ cell: 'abc' })
    expect(result).toEqual({
      ok: true,
      value: [
        {
          id: 'c1',
          name: 'Community c1',
          description: 'About c1',
          memberCount: 84,
          locationCell: 'cell:-23.56,-46.69',
          radiusKm: 5,
          allowPseudonyms: true,
          isMember: false,
          createdBy: { id: 'u9', name: 'alice' },
          createdAt: '2026-07-29T12:00:00Z',
        },
      ],
    })
    const wrapped = setup(() => ({ status: 200, data: { communities: [makeCommunityDto('c2', { description: null })] } }))
    const second = await wrapped.repository.listNearby('abc')
    expect(second.ok && second.value[0]).toMatchObject({ id: 'c2', description: '' })
  })

  it('posts the current cell and the pseudonym to join', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: {} }))
    const result = await repository.join({ communityId: 'c1', cell: 'abc', pseudonym: 'sambista' })
    expect(result.ok).toBe(true)
    expect(seen[0]!.url).toBe('/communities/c1/join')
    expect(JSON.parse(seen[0]!.data as string)).toEqual({ cell: 'abc', pseudonym: 'sambista' })
  })

  it('omits the pseudonym when there is none, and maps 403 to out-of-range', async () => {
    const ok = setup(() => ({ status: 200 }))
    await ok.repository.join({ communityId: 'c1', cell: 'abc' })
    expect(JSON.parse(ok.seen[0]!.data as string)).toEqual({ cell: 'abc' })
    const refused = setup(() => ({ status: 403 }))
    expect(await refused.repository.join({ communityId: 'c1', cell: 'abc' })).toEqual({ ok: false, error: 'out-of-range' })
  })

  it('creates a community with location_cell, radius and pseudonyms', async () => {
    const { repository, seen } = setup(() => ({ status: 201, data: makeCommunityDto('new') }))
    const result = await repository.create({ name: 'N', description: 'D', locationCell: 'abc', radiusKm: 5, allowPseudonyms: true })
    expect(result.ok).toBe(true)
    expect(seen[0]!.url).toBe('/communities')
    expect(JSON.parse(seen[0]!.data as string)).toEqual({ name: 'N', description: 'D', location_cell: 'abc', radius_km: 5, allow_pseudonyms: true })
  })

  it('omits location_cell when the community has no location', async () => {
    const { repository, seen } = setup(() => ({ status: 201, data: makeCommunityDto('new') }))
    await repository.create({ name: 'N', description: '', radiusKm: 5, allowPseudonyms: false })
    expect(JSON.parse(seen[0]!.data as string)).toEqual({ name: 'N', description: '', radius_km: 5, allow_pseudonyms: false })
  })

  it('reads a community feed page by cursor and maps 403 to forbidden', async () => {
    const page = setup(() => ({ status: 200, data: { posts: [makePostDto('p1')], next_cursor: 'n' } }))
    const result = await page.repository.feed({ communityId: 'c1', cursor: 'k' })
    expect(page.seen[0]!.url).toBe('/communities/c1/feed')
    expect(page.seen[0]!.params).toEqual({ cursor: 'k' })
    expect(result.ok && [result.value.posts[0]!.id, result.value.nextCursor]).toEqual(['p1', 'n'])
    const locked = setup(() => ({ status: 403 }))
    expect(await locked.repository.feed({ communityId: 'c1' })).toEqual({ ok: false, error: 'forbidden' })
  })

  it('gets one community', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: makeCommunityDto('c1', { is_member: true }) }))
    const result = await repository.get('c1')
    expect(seen[0]!.url).toBe('/communities/c1')
    expect(result.ok && result.value.isMember).toBe(true)
  })
})
