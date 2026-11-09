import { makeBrowserLocationProvider } from '../location/browser-geolocation'

/** What the browser does when asked: a position, a refusal, or silence. Null for a browser with no API at all. */
type Answer = { readonly lat: number; readonly lng: number } | { readonly code: number } | 'never' | null

const FIX = { lat: 40.7406, lng: -73.9599 }

/** The browser this test is pretending to be, until the next one says otherwise. */
function withBrowser(answer: Answer, permission: string | null = 'prompt') {
  const asked: { enableHighAccuracy: boolean; timeout: number; maximumAge: number }[] = []
  const geolocation =
    answer === null
      ? undefined
      : {
          getCurrentPosition: jest.fn(
            (
              success: (position: unknown) => void,
              fail: (error: unknown) => void,
              options: { enableHighAccuracy: boolean; timeout: number; maximumAge: number },
            ) => {
              asked.push(options)
              if (answer === 'never') return
              if ('lat' in answer) success({ coords: { latitude: answer.lat, longitude: answer.lng } })
              else fail({ code: answer.code })
            },
          ),
        }
  const permissions = permission === null ? undefined : { query: jest.fn(async () => ({ state: permission })) }
  Object.defineProperty(globalThis, 'navigator', { value: { geolocation, permissions }, configurable: true, writable: true })
  return { asked, geolocation, permissions }
}

const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')

beforeEach(() => jest.useFakeTimers())
afterEach(() => jest.useRealTimers())
afterAll(() => {
  if (original) Object.defineProperty(globalThis, 'navigator', original)
})

describe('makeBrowserLocationProvider', () => {
  it('reads the position the browser gives it', async () => {
    const { asked } = withBrowser(FIX)
    await expect(makeBrowserLocationProvider().currentPosition()).resolves.toEqual(FIX)
    // A 10 km radius does not need the GPS chip: a cached, tower-level fix answers it faster.
    expect(asked[0]).toEqual({ enableHighAccuracy: false, timeout: 12_000, maximumAge: 30_000 })
  })

  it('says no when the browser says no', async () => {
    withBrowser({ code: 1 })
    await expect(makeBrowserLocationProvider().currentPosition()).resolves.toBeNull()
  })

  it('says no when the browser has no answer, however long it is given', async () => {
    withBrowser('never')
    const pending = makeBrowserLocationProvider().currentPosition()
    await jest.advanceTimersByTimeAsync(12_000)
    await expect(pending).resolves.toBeNull()
  })

  it('says no when this browser has no geolocation at all', async () => {
    withBrowser(null)
    // Plain http over a LAN address: the browser never hands out the API, and there is no point asking.
    await expect(makeBrowserLocationProvider().status()).resolves.toEqual({ granted: false, canAskAgain: false })
    await expect(makeBrowserLocationProvider().currentPosition()).resolves.toBeNull()
  })

  it('reuses the fix from the permission dialog instead of asking the browser twice', async () => {
    const { geolocation } = withBrowser(FIX)
    const provider = makeBrowserLocationProvider()
    await expect(provider.currentPosition()).resolves.toEqual(FIX)
    await expect(provider.currentPosition()).resolves.toEqual(FIX)
    expect(geolocation!.getCurrentPosition).toHaveBeenCalledTimes(1)

    // A fix this old is somebody else's morning commute, so it goes and asks again.
    await jest.advanceTimersByTimeAsync(31_000)
    await expect(provider.currentPosition()).resolves.toEqual(FIX)
    expect(geolocation!.getCurrentPosition).toHaveBeenCalledTimes(2)
  })

  it('reports what the browser already knows about permission', async () => {
    withBrowser(FIX, 'granted')
    await expect(makeBrowserLocationProvider().status()).resolves.toEqual({ granted: true, canAskAgain: true })

    withBrowser(FIX, 'denied')
    await expect(makeBrowserLocationProvider().status()).resolves.toEqual({ granted: false, canAskAgain: false })

    withBrowser(FIX, 'prompt')
    await expect(makeBrowserLocationProvider().status()).resolves.toEqual({ granted: false, canAskAgain: true })
  })

  it('leaves asking open when the browser will not talk about permissions', async () => {
    withBrowser(FIX, null)
    await expect(makeBrowserLocationProvider().status()).resolves.toEqual({ granted: false, canAskAgain: true })
  })

  it('grants when asking the browser is what answers', async () => {
    withBrowser(FIX)
    await expect(makeBrowserLocationProvider().request()).resolves.toEqual({ granted: true, canAskAgain: true })
  })
})
