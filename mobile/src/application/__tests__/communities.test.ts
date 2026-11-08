import { err, ok, type CommunityRepository } from '../../domain'
import { makeCommunity, makeFakeCellEncoder, makePost } from '../../testing/fakes'
import { makeCreateCommunity, makeJoinCommunity, makeLoadCommunity, makeLoadNearbyCommunities } from '../communities'

const cellEncoder = makeFakeCellEncoder()
// "cell:lat,lng" centres, so one degree of latitude is about 111 km.
const anchored = (id: string, lat: number, radiusKm: number) => makeCommunity(id, { locationCell: `cell:${lat.toFixed(2)},0.00`, radiusKm })

const repo = (overrides: Partial<CommunityRepository> = {}): CommunityRepository => ({
  listJoined: async () => ok([]),
  listNearby: async () => ok([]),
  get: async (id) => ok(makeCommunity(id)),
  join: async () => ok(undefined),
  create: async () => ok(makeCommunity('new')),
  feed: async () => ok({ posts: [makePost('p')], nextCursor: null }),
  ...overrides,
})

describe('loadNearbyCommunities', () => {
  it('sorts by distance from the cell and flags communities beyond their radius', async () => {
    const listNearby = jest.fn(async () => ok([anchored('far', 0.5, 5), anchored('near', 0.01, 5), anchored('mid', 0.03, 5)]))
    const load = makeLoadNearbyCommunities({ communityRepository: repo({ listNearby }), cellEncoder })
    const result = await load({ cell: 'cell:0.00,0.00' })
    expect(listNearby).toHaveBeenCalledWith('cell:0.00,0.00')
    if (!result.ok) throw new Error('load failed')
    expect(result.value.map((c) => [c.id, c.inRange])).toEqual([
      ['near', true],
      ['mid', true],
      ['far', false],
    ])
  })

  it('passes a failure through', async () => {
    const load = makeLoadNearbyCommunities({ communityRepository: repo({ listNearby: async () => err('network') }), cellEncoder })
    expect(await load({ cell: 'x' })).toEqual({ ok: false, error: 'network' })
  })
})

describe('loadCommunity', () => {
  it('places the community from the cell, or marks it out of range without one', async () => {
    const communityRepository = repo({ get: async () => ok(anchored('c', 0.01, 5)) })
    const load = makeLoadCommunity({ communityRepository, cellEncoder })
    const placed = await load({ id: 'c', cell: 'cell:0.00,0.00' })
    expect(placed.ok && placed.value.inRange).toBe(true)
    const unlocated = await load({ id: 'c', cell: null })
    expect(unlocated.ok && [unlocated.value.inRange, unlocated.value.distanceKm]).toEqual([false, null])
  })
})

describe('joinCommunity', () => {
  it('sends the cell and a trimmed pseudonym, and drops a blank one', async () => {
    const join = jest.fn(async () => ok(undefined))
    const joinCommunity = makeJoinCommunity({ communityRepository: repo({ join }) })
    await joinCommunity({ communityId: 'c', cell: 'abc', pseudonym: '  sambista ' })
    expect(join).toHaveBeenLastCalledWith({ communityId: 'c', cell: 'abc', pseudonym: 'sambista' })
    await joinCommunity({ communityId: 'c', cell: 'abc', pseudonym: '   ' })
    expect(join).toHaveBeenLastCalledWith({ communityId: 'c', cell: 'abc' })
  })
})

describe('createCommunity', () => {
  it('validates the name before calling the repository', async () => {
    const create = jest.fn(async () => ok(makeCommunity('new')))
    const createCommunity = makeCreateCommunity({ communityRepository: repo({ create }) })
    expect(await createCommunity({ name: ' ', description: '', radiusKm: 5, allowPseudonyms: false })).toEqual({ ok: false, error: 'empty-name' })
    expect(create).not.toHaveBeenCalled()
    await createCommunity({ name: ' Vila ', description: ' d ', locationCell: 'abc', radiusKm: 5, allowPseudonyms: true })
    expect(create).toHaveBeenCalledWith({ name: 'Vila', description: 'd', locationCell: 'abc', radiusKm: 5, allowPseudonyms: true })
  })
})
