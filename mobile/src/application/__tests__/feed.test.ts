import { err, ok } from '../../domain'
import { makeFakeCellEncoder, makeFakeLocationProvider, makeFakePlaceNamer, makePost } from '../../testing/fakes'
import { makeCreatePost, makeListJoinedCommunities } from '../compose'
import { makeLoadFeed } from '../feed'
import { makeCellPlaceName, makeResolveLocation } from '../resolve-location'

const cellEncoder = makeFakeCellEncoder()

describe('resolveLocation', () => {
  it('returns the cell and the place name of its centroid when permission is granted', async () => {
    const { provider } = makeFakeLocationProvider({ granted: true })
    const { namer, calls } = makeFakePlaceNamer()
    const result = await makeResolveLocation({ locationProvider: provider, cellEncoder, placeNamer: namer })({ prompt: true })
    expect(result).toEqual({ ok: true, value: { cell: 'cell:-23.56,-46.69', placeName: 'Pinheiros, São Paulo' } })
    expect(calls).toEqual([{ lat: -23.56, lng: -46.69 }])
  })

  it('asks for permission when prompting is allowed', async () => {
    const { provider, calls } = makeFakeLocationProvider({ granted: false, grantOnRequest: true })
    const result = await makeResolveLocation({ locationProvider: provider, cellEncoder, placeNamer: makeFakePlaceNamer().namer })({ prompt: true })
    expect(result.ok).toBe(true)
    expect(calls.request).toBe(1)
  })

  it('reports denied permission, without prompting when asked not to', async () => {
    const { provider, calls } = makeFakeLocationProvider({ granted: false })
    const resolve = makeResolveLocation({ locationProvider: provider, cellEncoder, placeNamer: makeFakePlaceNamer().namer })
    expect(await resolve({ prompt: false })).toEqual(err({ kind: 'denied', canAskAgain: true }))
    expect(calls.request).toBe(0)
  })

  it('reports a denied permission that cannot be asked again', async () => {
    const { provider } = makeFakeLocationProvider({ granted: false, canAskAgain: false })
    const resolve = makeResolveLocation({ locationProvider: provider, cellEncoder, placeNamer: makeFakePlaceNamer().namer })
    expect(await resolve({ prompt: true })).toEqual(err({ kind: 'denied', canAskAgain: false }))
  })

  it('reports an unreadable position', async () => {
    const { provider } = makeFakeLocationProvider({ granted: true, position: null })
    const resolve = makeResolveLocation({ locationProvider: provider, cellEncoder, placeNamer: makeFakePlaceNamer().namer })
    expect(await resolve({ prompt: true })).toEqual(err({ kind: 'unavailable' }))
  })
})

describe('placeNameOf', () => {
  it('looks a cell up once', async () => {
    const { namer, calls } = makeFakePlaceNamer('Vila Madalena')
    const nameOf = makeCellPlaceName({ cellEncoder, placeNamer: namer })
    expect(await Promise.all([nameOf('cell:1.00,2.00'), nameOf('cell:1.00,2.00')])).toEqual(['Vila Madalena', 'Vila Madalena'])
    expect(calls).toHaveLength(1)
  })
})

describe('loadFeed', () => {
  it('queries the cell with the 10 km radius and the cursor', async () => {
    const list = jest.fn().mockResolvedValue(ok({ posts: [makePost('a')], nextCursor: 'c2' }))
    const result = await makeLoadFeed({ feedRepository: { list } })({ cell: 'x', cursor: 'c1' })
    expect(list).toHaveBeenCalledWith({ cell: 'x', radiusKm: 10, cursor: 'c1' })
    expect(result.ok && result.value.nextCursor).toBe('c2')
  })
})

describe('createPost', () => {
  it('trims the body and sends the location cell when given', async () => {
    const create = jest.fn().mockResolvedValue(ok(makePost('n')))
    const result = await makeCreatePost({ postRepository: { create } })({ body: ' hi ', locationCell: 'x', communityId: 'c' })
    expect(result.ok).toBe(true)
    expect(create).toHaveBeenCalledWith({ body: 'hi', locationCell: 'x', communityId: 'c' })
  })

  it('does not call the server for blank or over-long bodies', async () => {
    const create = jest.fn()
    const createPost = makeCreatePost({ postRepository: { create } })
    expect(await createPost({ body: '  ' })).toEqual(err('empty'))
    expect(await createPost({ body: 'x'.repeat(501) })).toEqual(err('too-long'))
    expect(create).not.toHaveBeenCalled()
  })
})

describe('listJoinedCommunities', () => {
  it('passes through the repository result', async () => {
    const listJoined = jest.fn().mockResolvedValue(ok([{ id: '1', name: 'Vizinhos' }]))
    expect(await makeListJoinedCommunities({ communityRepository: { listJoined } })()).toEqual(ok([{ id: '1', name: 'Vizinhos' }]))
  })
})
