import { useCallback, useEffect, useRef, useState } from 'react'
import { AppState } from 'react-native'

import { appendPage, bufferPost, prependPosts, type Post } from '../domain'
import { useUseCases } from './use-cases'

export type FeedPhase = 'locating' | 'denied' | 'ready'

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
}

/** Location → H3 cell → paginated feed plus the live stream of new posts for that cell. */
export function useFeed() {
  const { resolveLocation, loadFeed, subscribeToPosts } = useUseCases()
  const [state, setState] = useState<FeedState>(initial)
  const cursor = useRef<string | null>(null)
  const generation = useRef(0)
  const loadingMore = useRef(false)

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

  useEffect(() => {
    // start() only sets state after the first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start(true)
  }, [start])

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
    await start(false)
    patch({ refreshing: false })
  }, [start, patch])

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

  return { state, enableLocation: () => start(true), refresh, loadMore, showPending }
}
