import type { LatLng, LocationProvider } from '../../domain'

/**
 * The web build asks the browser for a position directly instead of through expo-location.
 *
 * Two things go wrong on the web otherwise: `getForegroundPermissionsAsync` needs the Permissions
 * API, which is missing on some browsers, and `getCurrentPositionAsync` accepts a fix of any age,
 * so a fix cached days ago is handed back as if it were now. Talking to the browser keeps the
 * answer honest, and the clock below is what stops a dialog nobody answered from hanging the feed.
 */

/** How long to wait for the person to answer the browser's dialog, not just for the fix itself. */
const TIMEOUT_MS = 12_000

/** A fix read while asking for permission is reused for this long, so asking is one round trip. */
const FRESH_MS = 30_000

type BrowserPosition = { readonly coords: { readonly latitude: number; readonly longitude: number } }
type BrowserGeolocation = {
  getCurrentPosition: (
    ok: (position: BrowserPosition) => void,
    fail: (error: unknown) => void,
    options: { enableHighAccuracy: boolean; timeout: number; maximumAge: number },
  ) => void
}

/** The browser's own position API, or nothing at all. Over plain http it is not handed out: https only. */
const geolocation = (): BrowserGeolocation | null =>
  (globalThis as { navigator?: { geolocation?: BrowserGeolocation } }).navigator?.geolocation ?? null

/** 'prompt' until the person has answered once, then whatever they chose. Null when the browser has no Permissions API. */
const permissionState = async (): Promise<string | null> => {
  try {
    const status = await globalThis.navigator?.permissions?.query({ name: 'geolocation' })
    return status?.state ?? null
  } catch {
    // Safari and Firefox refuse names they do not track, which is not an answer about location.
    return null
  }
}

/** Ask the browser once. Null for every no: refused, unavailable, timed out, or no API here. */
const read = (): Promise<LatLng | null> =>
  new Promise((resolve) => {
    const api = geolocation()
    if (!api) return resolve(null)
    let settled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    // The timeout option covers waiting for a fix; waiting for a person to answer the dialog is on us.
    const done = (fix: LatLng | null) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(fix)
    }
    timer = setTimeout(() => done(null), TIMEOUT_MS)
    api.getCurrentPosition(
      ({ coords }) => done({ lat: coords.latitude, lng: coords.longitude }),
      () => done(null),
      // Wi-Fi and IP positioning is good enough for a 10 km radius and answers in a second.
      { enableHighAccuracy: false, timeout: TIMEOUT_MS, maximumAge: FRESH_MS },
    )
  })

export const makeBrowserLocationProvider = (): LocationProvider => {
  /** The fix from the last ask, spent on the next read so that a later refresh goes back to the browser. */
  let asked: { at: number; fix: LatLng } | null = null

  /** One ask, one dialog: in the browser, permission and position come from the same call. */
  const readOnce = async (): Promise<LatLng | null> => {
    if (asked && Date.now() - asked.at < FRESH_MS) {
      const fix = asked.fix
      asked = null
      return fix
    }
    asked = null
    const fix = await read()
    if (fix) asked = { at: Date.now(), fix }
    return fix
  }

  return {
    async status() {
      if (!geolocation()) return { granted: false, canAskAgain: false }
      const state = await permissionState()
      // With no Permissions API the only way to find out is to ask, so say it is still worth asking.
      if (state === null) return { granted: false, canAskAgain: true }
      return { granted: state === 'granted', canAskAgain: state !== 'denied' }
    },
    async request() {
      // Asking for permission and reading the position is the same call in the browser.
      const fix = await readOnce()
      return { granted: fix !== null, canAskAgain: true }
    },
    currentPosition: readOnce,
  }
}
