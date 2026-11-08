import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState, Platform } from 'react-native'

import { appendPage, bufferPost, postalCodeMessage, prependPosts, type Post } from '../domain'
import { useUseCases } from './use-cases'

/** The web has no GPS, so the user names their place with a postal code instead. */
export const usesPostalCode = (): boolean => Platform.OS === 'web'

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
}

/** Location → H3 cell → paginated feed plus the live stream of new posts for that cell. */
export function useFeed() {
  const { resolveLocation, resolvePostalCode, readPostalCode, loadFeed, subscribeToPosts } = useUseCases()
  const [state, setState] = useState<FeedState>(initial)
  const cursor = useRef<string | null>(null)
  const generation = useRef(0)
  const loadingMore = useRef(false)
  /** The postal code the feed is currently reading, so a refresh does not have to ask storage. */
  const code = useRef<string | null>(null)

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
      code.current = area.value.postalCode
      const { cell, placeName } = area.value
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
    async (prompt: boolean) => {
      const location = await resolveLocation({ prompt })
      if (!location.ok) {
        if (location.error.kind === 'denied') patch({ phase: 'denied', canAskAgain: location.error.canAskAgain, refreshing: false })
        else patch({ phase: 'ready', failed: true, refreshing: false })
        return
      }
      const { cell, placeName } = location.value
      setState((s) => (s.cell === cell ? { ...s, phase: 'ready', placeName } : { ...s, phase: 'ready', cell, placeName, posts: [], pending: [] }))
      await loadFirstPage(cell)
    },
    [resolveLocation, loadFirstPage, patch],
  )

  /** Reopens on the saved postal code, or asks for one when the user never chose a place. */
  const startFromPostalCode = useCallback(async () => {
    const saved = await readPostalCode()
    if (!saved) return patch({ phase: 'ask' })
    await applyPostalCode(saved)
  }, [readPostalCode, applyPostalCode, patch])

  useEffect(() => {
    // start() only sets state after the first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void (usesPostalCode() ? startFromPostalCode() : start(true))
  }, [start, startFromPostalCode])

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
    if (usesPostalCode()) {
      if (code.current) await applyPostalCode(code.current)
    } else {
      await start(false)
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

  /** The web: read the feed of a typed postal code. */
  const setPostalCode = useCallback((raw: string) => void applyPostalCode(raw), [applyPostalCode])
  /** The web: back to the prompt; the current feed stays put until a new place resolves. */
  const changePlace = useCallback(() => setState((s) => ({ ...s, phase: 'ask', placeError: null })), [])
  /** The web: leave the prompt without choosing a new place. */
  const backToFeed = useCallback(() => setState((s) => ({ ...s, phase: s.cell ? 'ready' : 'ask', placeError: null })), [])

  return { state, enableLocation: () => start(true), setPostalCode, changePlace, backToFeed, refresh, loadMore, showPending }
}
