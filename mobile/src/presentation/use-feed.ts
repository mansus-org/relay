import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState, Platform } from 'react-native'

import { appendPage, bufferPost, postalCodeMessage, prependPosts, type Post } from '../domain'
import { useUseCases } from './use-cases'

/** The web has no GPS of its own; the browser gets asked instead, and a postal code covers the rest. */
export const usesPostalCode = (): boolean => Platform.OS === 'web'

/** Whether the browser can be asked where it is. It cannot over plain http, where the API is not handed out. */
const browserOffersLocation = (): boolean => typeof navigator !== 'undefined' && !!navigator.geolocation

/** What to say when the browser would not answer, next to the field that still can. */
const NOT_LOCATING = 'Your browser would not say where you are. Try a postal code.'

export type FeedPhase =
  | 'locating'
  /** Waiting for a postal code; the web only, and only until one is chosen. */
  | 'ask'
  | 'denied'
  | 'ready'

export type FeedState = {
  phase: FeedPhase
  canAskAgain: boolean
  cell: string | null
  placeName: string | null
  posts: readonly Post[]
  /** Streamed posts not yet shown; the banner reveals them. */
  pending: readonly Post[]
  refreshing: boolean
  loadingMore: boolean
  hasMore: boolean
  /** True when the last load failed with nothing to show. */
  failed: boolean
  /** What to say under the postal-code field; null when there is nothing to say. */
  placeError: string | null
  /** A postal-code lookup is in flight. */
  checking: boolean
  /** The web: a "use my location" press is waiting on the browser. */
  askingBrowser: boolean
}

const initial: FeedState = {
  phase: 'locating',
  canAskAgain: true,
  cell: null,
  placeName: null,
  posts: [],
  pending: [],
  refreshing: false,
  loadingMore: false,
  hasMore: false,
  failed: false,
  placeError: null,
  checking: false,
  askingBrowser: false,
}

export type FeedOptions = {
  /** A place named in the URL (`/?code=15007`). It wins over the stored one and is read once. */
  readonly requestedCode?: string | null
  /** Reports the code the feed opened, so the address bar can follow the place. */
  readonly onPlaced?: (code: string) => void
}

/** Location → H3 cell → paginated feed plus the live stream of new posts for that cell. */
export function useFeed(options: FeedOptions = {}) {
  const { resolveLocation, resolvePostalCode, readPostalCode, loadFeed, subscribeToPosts } = useUseCases()
  // The address is read once, and the callback is kept in a ref: a caller that re-renders with a
  // fresh function or a param that has since gone away must not drag the feed back to the URL.
  const [requestedCode] = useState(() => options.requestedCode ?? null)
  const placed = useRef(options.onPlaced)
  useEffect(() => {
    placed.current = options.onPlaced
  }, [options.onPlaced])
  const [state, setState] = useState<FeedState>(initial)
  const cursor = useRef<string | null>(null)
  const generation = useRef(0)
  const loadingMore = useRef(false)
  /** The postal code the feed is currently reading, so a refresh does not have to ask storage. */
  const code = useRef<string | null>(null)
  /** Where the feed is reading from, so a refresh goes back to the same place the same way. */
  const source = useRef<'located' | 'code' | null>(null)
  /** Set once the person names a place themselves; a browser answer that arrives after that is too late. */
  const chosen = useRef(false)
  /** Offered on the web prompt only when the browser can actually be asked. */
  const [canUseBrowserLocation] = useState(() => usesPostalCode() && browserOffersLocation())

  const patch = useCallback((next: Partial<FeedState>) => setState((s) => ({ ...s, ...next })), [])

  const loadFirstPage = useCallback(
    async (cell: string) => {
      const ticket = ++generation.current
      const result = await loadFeed({ cell })
      if (ticket !== generation.current) return
      if (result.ok) {
        cursor.current = result.value.nextCursor
        patch({ posts: result.value.posts, pending: [], hasMore: result.value.nextCursor !== null, failed: false })
      } else {
        patch({ failed: true })
      }
    },
    [loadFeed, patch],
  )

  /** Resolves a typed postal code and points the feed at it. A failed lookup leaves the feed alone. */
  const applyPostalCode = useCallback(
    async (raw: string) => {
      chosen.current = true
      patch({ checking: true, placeError: null })
      const area = await resolvePostalCode(raw)
      if (!area.ok) {
        setState((s) => ({
          ...s,
          checking: false,
          placeError: postalCodeMessage(area.error),
          ...(s.cell ? {} : { phase: 'ask' as const }),
        }))
        return
      }
      const { cell, placeName, postalCode } = area.value
      source.current = 'code'
      code.current = postalCode
      placed.current?.(postalCode)
      setState((s) =>
        s.cell === cell
          ? { ...s, phase: 'ready', checking: false, placeName }
          : { ...s, phase: 'ready', checking: false, cell, placeName, posts: [], pending: [] },
      )
      await loadFirstPage(cell)
    },
    [resolvePostalCode, loadFirstPage, patch],
  )

  /** Resolves the location, then loads the feed. `prompt` allows the permission dialog. */
  const start = useCallback(
    async (prompt: boolean, onRefused?: () => void, unless?: () => boolean) => {
      const location = await resolveLocation({ prompt })
      // Whoever chose a place while the browser was thinking has already answered for themselves.
      if (unless?.()) return
      if (!location.ok) {
        // Only the web passes a fallback; a phone has nowhere to go but its own settings.
        if (onRefused) return onRefused()
        if (location.error.kind === 'denied') patch({ phase: 'denied', canAskAgain: location.error.canAskAgain, refreshing: false })
        else patch({ phase: 'ready', failed: true, refreshing: false })
        return
      }
      source.current = 'located'
      const { cell, placeName } = location.value
      setState((s) => (s.cell === cell ? { ...s, phase: 'ready', placeName } : { ...s, phase: 'ready', cell, placeName, posts: [], pending: [] }))
      await loadFirstPage(cell)
    },
    [resolveLocation, loadFirstPage, patch],
  )

  /** Reopens on the saved postal code, or asks for one when the user never chose a place. */
  const startFromPostalCode = useCallback(async () => {
    const saved = requestedCode ?? (await readPostalCode())
    if (!saved) return patch({ phase: 'ask' })
    await applyPostalCode(saved)
  }, [readPostalCode, applyPostalCode, patch, requestedCode])

  /** The web: the browser knows where it is more often than not, and the postal code covers the rest. */
  const startFromBrowser = useCallback(async () => {
    // The address already names a place; someone who followed a link to it should not be prompted for one.
    if (requestedCode) return startFromPostalCode()
    await start(true, () => void startFromPostalCode(), () => chosen.current)
  }, [requestedCode, start, startFromPostalCode])

  useEffect(() => {
    // start() only sets state after the first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void (usesPostalCode() ? startFromBrowser() : start(true))
  }, [start, startFromBrowser])

  // Returning from the system settings screen after granting permission.
  const denied = state.phase === 'denied'
  useEffect(() => {
    if (!denied) return
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') void start(false)
    })
    return () => sub.remove()
  }, [denied, start])

  const { cell } = state
  useEffect(() => {
    if (!cell) return
    return subscribeToPosts(cell, (post) =>
      setState((s) => (s.posts.some((p) => p.id === post.id) ? s : { ...s, pending: bufferPost(s.pending, post) })),
    )
  }, [cell, subscribeToPosts])

  const refresh = useCallback(async () => {
    patch({ refreshing: true })
    if (!usesPostalCode()) await start(false)
    else if (source.current !== 'located') {
      if (code.current) await applyPostalCode(code.current)
    } else {
      // Back to the browser that opened it, or to the code it fell back on once the browser stopped answering.
      await start(false, () => {
        if (code.current) void applyPostalCode(code.current)
        else patch({ phase: 'ask', placeError: NOT_LOCATING })
      })
    }
    patch({ refreshing: false })
  }, [start, applyPostalCode, patch])

  const loadMore = useCallback(async () => {
    if (!cell || !cursor.current || loadingMore.current) return
    loadingMore.current = true
    patch({ loadingMore: true })
    const ticket = generation.current
    const result = await loadFeed({ cell, cursor: cursor.current })
    loadingMore.current = false
    if (ticket !== generation.current) return patch({ loadingMore: false })
    if (result.ok) {
      cursor.current = result.value.nextCursor
      const page = result.value.posts
      setState((s) => ({ ...s, posts: appendPage(s.posts, page), hasMore: result.value.nextCursor !== null, loadingMore: false }))
    } else {
      patch({ loadingMore: false })
    }
  }, [cell, loadFeed, patch])

  const showPending = useCallback(
    () => setState((s) => ({ ...s, posts: prependPosts(s.posts, s.pending), pending: [] })),
    [],
  )

  /** The web: ask the browser again from the prompt, and say so when it still will not answer. */
  const useBrowserLocation = useCallback(async () => {
    patch({ askingBrowser: true, placeError: null })
    await start(true, () => patch({ phase: 'ask', placeError: NOT_LOCATING }))
    patch({ askingBrowser: false })
  }, [start, patch])

  /** The web: read the feed of a typed postal code. */
  const setPostalCode = useCallback((raw: string) => void applyPostalCode(raw), [applyPostalCode])
  /** The web: back to the prompt; the current feed stays put until a new place resolves. */
  const changePlace = useCallback(() => {
    chosen.current = true
    setState((s) => ({ ...s, phase: 'ask', placeError: null }))
  }, [])
  /** The web: leave the prompt without choosing a new place. */
  const backToFeed = useCallback(() => setState((s) => ({ ...s, phase: s.cell ? 'ready' : 'ask', placeError: null })), [])

  return {
    state,
    enableLocation: () => start(true),
    useBrowserLocation,
    canUseBrowserLocation,
    setPostalCode,
    changePlace,
    backToFeed,
    refresh,
    loadMore,
    showPending,
  }
}
