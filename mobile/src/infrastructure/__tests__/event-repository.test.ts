import { makeFakeServer, type FakeHandler } from '../../testing/fake-server'
import { makeHttpClient } from '../http/client'
import { makeHttpEventRepository } from '../http/event-repository'

function setup(handler: FakeHandler) {
  const server = makeFakeServer(handler)
  const http = makeHttpClient({
    getBaseUrl: async () => 'https://x/api',
    getAccessToken: async () => 't',
    refreshAccessToken: async () => null,
    onUnauthorized: () => {},
  })
  http.defaults.adapter = server.adapter
  return { repository: makeHttpEventRepository({ http }), seen: server.seen }
}

const dto = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  host_id: 'u-1',
  host_name: 'Ana',
  title: 'Sunday market',
  starts_at: '2026-11-25T19:30:00+00:00',
  ...extra,
})

describe('event repository', () => {
  it('reads a page of events for a cell, and keeps the cursor for the next one', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: { events: [dto('e-1')], next_from: '2026-11-26T19:30:00+00:00|e-1' } }))
    const result = await repository.list({ cell: 'abc', radiusKm: 10, from: '2026-11-25' })

    expect(seen[0]!.url).toBe('/events')
    expect(seen[0]!.params).toEqual({ cell: 'abc', radius: 10, from: '2026-11-25' })
    expect(result.ok && result.value.nextFrom).toBe('2026-11-26T19:30:00+00:00|e-1')
  })

  it('names the row the way the app reads it, and treats a blank as nothing', async () => {
    const { repository } = setup(() => ({ status: 200, data: { events: [dto('e-1', { venue_name: null, rsvp_count: 4 })] } }))
    const result = await repository.list({ cell: 'abc', radiusKm: 10 })

    expect(result.ok && result.value.events[0]).toEqual({
      id: 'e-1',
      hostId: 'u-1',
      hostName: 'Ana',
      title: 'Sunday market',
      startsAt: '2026-11-25T19:30:00+00:00',
      endsAt: null,
      venueName: null,
      details: null,
      locationCell: null,
      communityId: null,
      communityName: null,
      rsvpCount: 4,
    })
  })

  it('keeps the community an event is filed under', async () => {
    const { repository } = setup(() => ({ status: 200, data: { events: [dto('e-1', { community_id: 'c-1', community_name: 'Vila Madalena' })] } }))
    const result = await repository.list({ cell: 'abc', radiusKm: 10 })

    expect(result.ok && result.value.events[0]).toMatchObject({ communityId: 'c-1', communityName: 'Vila Madalena' })
  })

  it('reads the events filed under one community, from where the reader is standing', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: { events: [dto('e-1')], next_from: '2026-11-26T19:30:00+00:00|e-1' } }))
    const result = await repository.listForCommunity({ communityId: 'c-1', cell: 'abc', from: '2026-11-25' })

    expect(seen[0]!.url).toBe('/communities/c-1/events')
    expect(seen[0]!.params).toEqual({ cell: 'abc', from: '2026-11-25' })
    expect(result.ok && result.value).toEqual({ events: [expect.objectContaining({ id: 'e-1' })], nextFrom: '2026-11-26T19:30:00+00:00|e-1' })
  })

  it('says the community is gone rather than showing an empty list of its events', async () => {
    expect(await setup(() => ({ status: 404 })).repository.listForCommunity({ communityId: 'c-1', cell: 'abc' })).toEqual({ ok: false, error: 'not-found' })
  })

  it('does not call a dead network an empty list', async () => {
    expect(await setup(() => ({ status: 500 })).repository.listForCommunity({ communityId: 'c-1', cell: 'abc' })).toEqual({ ok: false, error: 'unexpected' })
  })

  it('takes an empty list as an empty page, not a broken one', async () => {
    const { repository } = setup(() => ({ status: 200, data: {} }))
    expect(await repository.list({ cell: 'abc', radiusKm: 10 })).toEqual({ ok: true, value: { events: [], nextFrom: null } })
  })

  it('asks for today without inventing a from it was not given', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: { events: [] } }))
    await repository.list({ cell: 'abc', radiusKm: 5 })

    expect(seen[0]!.params).toEqual({ cell: 'abc', radius: 5 })
  })

  it('says whether the reader is going, which only the detail answers', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: dto('e-1', { user_rsvped: true }) }))
    const result = await repository.get('e-1')

    expect(seen[0]!.url).toBe('/events/e-1')
    expect(result.ok && result.value.userRsvped).toBe(true)
  })

  it('sends an event out the way the server spells it, and leaves out what was not filled in', async () => {
    const { repository, seen } = setup(() => ({ status: 201, data: dto('e-2') }))
    await repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z', venueName: '', locationCell: 'abc' })

    expect(JSON.parse(seen[0]!.data)).toEqual({ title: 'Sunday market', starts_at: '2026-11-25T19:30:00Z', location_cell: 'abc' })
  })

  it('keeps an end and a venue once the host gave them', async () => {
    const { repository, seen } = setup(() => ({ status: 201, data: dto('e-2') }))
    await repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z', endsAt: '2026-11-25T22:00:00Z', venueName: 'The back room', details: 'Bring something.' })

    expect(JSON.parse(seen[0]!.data)).toEqual({
      title: 'Sunday market',
      starts_at: '2026-11-25T19:30:00Z',
      ends_at: '2026-11-25T22:00:00Z',
      venue_name: 'The back room',
      details: 'Bring something.',
    })
  })

  it('sends the community it is filed under, and nothing when it is not', async () => {
    const filed = setup(() => ({ status: 201, data: dto('e-2') }))
    const loose = setup(() => ({ status: 201, data: dto('e-2') }))
    await filed.repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z', communityId: 'c-1' })
    await loose.repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z' })

    expect(JSON.parse(filed.seen[0]!.data)).toEqual({ title: 'Sunday market', starts_at: '2026-11-25T19:30:00Z', community_id: 'c-1' })
    expect(JSON.parse(loose.seen[0]!.data)).not.toHaveProperty('community_id')
  })

  it('says who turned the event away when it was the community', async () => {
    const stranger = setup(() => ({ status: 403 }))
    const vanished = setup(() => ({ status: 404 }))

    expect(await stranger.repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z', communityId: 'c-1' })).toEqual({ ok: false, error: 'not-a-member' })
    expect(await vanished.repository.create({ title: 'Sunday market', startsAt: '2026-11-25T19:30:00Z', communityId: 'c-1' })).toEqual({ ok: false, error: 'not-found' })
  })

  it('answers with the head count after the place was saved', async () => {
    const { repository, seen } = setup(() => ({ status: 200, data: { event_id: 'e-1', rsvp_count: 5 } }))
    expect(await repository.rsvp('e-1')).toEqual({ ok: true, value: 5 })
    expect(seen[0]!.url).toBe('/events/e-1/rsvp')
  })

  it('says a second place is not a second place', async () => {
    const { repository } = setup(() => ({ status: 409 }))
    expect(await repository.rsvp('e-1')).toEqual({ ok: false, error: 'already-going' })
  })

  it('takes a place back with a delete, and means it when there was nothing to take', async () => {
    const gone = setup(() => ({ status: 404 }))
    const taken = setup(() => ({ status: 200, data: {} }))
    await gone.repository.cancelRsvp('e-1')
    const result = await taken.repository.cancelRsvp('e-1')

    expect(taken.seen[0]!.method).toBe('delete')
    expect(taken.seen[0]!.url).toBe('/events/e-1/rsvp')
    expect(result).toEqual({ ok: true, value: undefined })
    expect(await gone.repository.cancelRsvp('e-1')).toEqual({ ok: false, error: 'not-going' })
  })

  it('says an event is gone, and says so about the event that was asked for', async () => {
    expect(await setup(() => ({ status: 404 })).repository.get('e-1')).toEqual({ ok: false, error: 'not-found' })
  })

  it('asks for a sign in before it lets you at an event', async () => {
    expect(await setup(() => ({ status: 401 })).repository.rsvp('e-1')).toEqual({ ok: false, error: 'unauthorized' })
  })

  it('does not call a dead network a missing event', async () => {
    expect(await setup(() => ({ status: 500 })).repository.get('e-1')).toEqual({ ok: false, error: 'unexpected' })
  })
})
