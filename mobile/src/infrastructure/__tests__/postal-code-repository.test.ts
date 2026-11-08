import { AxiosError } from 'axios'

import { makeHttpClient } from '../http/client'
import { makeHttpPostalCodeResolver } from '../http/postal-code-repository'
import { makeFakeServer, urlOf, type FakeHandler } from '../../testing/fake-server'

function setup(handler: FakeHandler) {
  const { adapter, seen } = makeFakeServer(handler)
  const http = makeHttpClient({
    getBaseUrl: async () => 'https://x/api',
    getAccessToken: async () => 't',
    refreshAccessToken: async () => null,
    onUnauthorized: () => {},
  })
  http.defaults.adapter = adapter
  return { resolver: makeHttpPostalCodeResolver({ http }), seen, http }
}

const vigo = { postal_code: '36201', place_name: 'Vigo', cell: '891e2500000ffff' }

describe('postal code repository', () => {
  it('asks for the code and maps the place', async () => {
    const { resolver, seen } = setup(() => ({ status: 200, data: vigo }))
    expect(await resolver.resolve('36201')).toEqual({ ok: true, value: { postalCode: '36201', placeName: 'Vigo', cell: '891e2500000ffff' } })
    expect(urlOf(seen[0]!)).toBe('https://x/api/location/postal-code/36201')
  })

  it.each([
    [400, 'invalid'],
    [404, 'not-found'],
    [503, 'unavailable'],
  ])('passes the reason through on %s', async (status, reason) => {
    const { resolver } = setup(() => ({ status, data: { detail: 'Relay is in Galicia for now.' } }))
    expect(await resolver.resolve('28001')).toEqual({ ok: false, error: { reason, message: 'Relay is in Galicia for now.' } })
  })

  it('has no message of its own when the server sends none', async () => {
    const { resolver } = setup(() => ({ status: 500, data: {} }))
    expect(await resolver.resolve('36201')).toEqual({ ok: false, error: { reason: 'unexpected', message: '' } })
  })

  it('ignores a detail that is not a sentence', async () => {
    const { resolver } = setup(() => ({ status: 404, data: { detail: { why: 'nope' } } }))
    expect(await resolver.resolve('36201')).toEqual({ ok: false, error: { reason: 'not-found', message: '' } })
  })

  it('calls a failed connection a network problem', async () => {
    const { http } = setup(() => ({ status: 200 }))
    http.defaults.adapter = async (config) => Promise.reject(new AxiosError('down', 'ECONNREFUSED', config))
    expect(await makeHttpPostalCodeResolver({ http }).resolve('36201')).toEqual({ ok: false, error: { reason: 'network', message: '' } })
  })
})
