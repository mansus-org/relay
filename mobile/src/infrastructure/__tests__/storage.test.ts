import { DEFAULT_SERVER_URL } from '../../domain'
import { makeMemoryStorage } from '../../testing/fakes'
import { makeServerUrlStore, SERVER_URL_KEY } from '../storage/server-url-store'
import { makePostalCodeStore, POSTAL_CODE_KEY } from '../storage/postal-code-store'
import { ACCESS_TOKEN_KEY, makeTokenStore, REFRESH_TOKEN_KEY } from '../storage/token-store'
import { makeSessionEvents } from '../session-events'

describe('token store', () => {
  it('loads null when there is no access token', async () => {
    const storage = makeMemoryStorage({ [REFRESH_TOKEN_KEY]: 'r' })
    expect(await makeTokenStore({ storage }).load()).toBeNull()
  })

  it('round-trips both tokens', async () => {
    const store = makeTokenStore({ storage: makeMemoryStorage() })
    await store.save({ accessToken: 'a', refreshToken: 'r' })
    expect(await store.load()).toEqual({ accessToken: 'a', refreshToken: 'r' })
  })

  it('leaves the refresh token untouched when saving without one', async () => {
    const storage = makeMemoryStorage()
    const store = makeTokenStore({ storage })
    await store.save({ accessToken: 'a1', refreshToken: 'r1' })
    await store.save({ accessToken: 'a2' })
    expect(storage.data.get(ACCESS_TOKEN_KEY)).toBe('a2')
    expect(storage.data.get(REFRESH_TOKEN_KEY)).toBe('r1')
  })

  it('clears both tokens', async () => {
    const storage = makeMemoryStorage()
    const store = makeTokenStore({ storage })
    await store.save({ accessToken: 'a', refreshToken: 'r' })
    await store.clear()
    expect(storage.data.size).toBe(0)
  })
})

describe('server URL store', () => {
  it('falls back to the default URL', async () => {
    expect(await makeServerUrlStore({ storage: makeMemoryStorage() }).get()).toBe(DEFAULT_SERVER_URL)
  })

  it('returns the stored URL', async () => {
    const storage = makeMemoryStorage()
    const store = makeServerUrlStore({ storage })
    await store.set('https://friends.example')
    expect(storage.data.get(SERVER_URL_KEY)).toBe('https://friends.example')
    expect(await store.get()).toBe('https://friends.example')
  })
})

describe('postal code store', () => {
  it('has no place until one is chosen', async () => {
    expect(await makePostalCodeStore({ storage: makeMemoryStorage() }).read()).toBeNull()
  })

  it('keeps the last place chosen', async () => {
    const storage = makeMemoryStorage()
    const store = makePostalCodeStore({ storage })
    await store.save('36201')
    await store.save('15003')
    expect(storage.data.get(POSTAL_CODE_KEY)).toBe('15003')
    expect(await store.read()).toBe('15003')
  })
})

describe('session events', () => {
  it('notifies subscribers until they unsubscribe', () => {
    const events = makeSessionEvents()
    const handler = jest.fn()
    const off = events.onExpired(handler)
    events.notifyExpired()
    off()
    events.notifyExpired()
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
