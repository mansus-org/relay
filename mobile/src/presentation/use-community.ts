import { useCallback, useEffect, useRef, useState } from 'react'

import { appendPage, editPost, type CommunityError, type NearbyCommunity, type Post } from '../domain'
import { useUseCases } from './use-cases'
import { useReaction, type EditPost } from './use-reaction'

export type CommunityState = {
  /** False until the community itself has loaded (or failed to). */
  loaded: boolean
  community: NearbyCommunity | null
  /** True when the device position is unavailable, so the user cannot join. */
  noLocation: boolean
  posts: readonly Post[]
  feedLoaded: boolean
  refreshing: boolean
  loadingMore: boolean
  hasMore: boolean
  /** The community could not be loaded. */
  failed: boolean
  /** The feed could not be loaded; shown with an empty list. */
  feedFailed: boolean
}

const initial: CommunityState = {
  loaded: false,
  community: null,
  noLocation: false,
  posts: [],
  feedLoaded: false,
  refreshing: false,
  loadingMore: false,
  hasMore: false,
  failed: false,
  feedFailed: false,
}

/** One community: details placed from the user's cell, its feed once joined, and the join flow. */
export function useCommunity(id: string) {
  const { resolveLocation, loadCommunity, loadCommunityFeed, joinCommunity } = useUseCases()
  const [state, setState] = useState<CommunityState>(initial)
  const [cell, setCell] = useState<string | null>(null)
  const [promptOpen, setPromptOpen] = useState(false)
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState<CommunityError | null>(null)
  const cursor = useRef<string | null>(null)
  const generation = useRef(0)
  const loadingMore = useRef(false)

  const patch = useCallback((next: Partial<CommunityState>) => setState((s) => ({ ...s, ...next })), [])

  // A reaction goes on the card it was tapped on, and settles on whatever the server counted.
  const edit = useCallback<EditPost>((postId, next) => setState((s) => ({ ...s, posts: editPost(s.posts, postId, next) })), [])
  const react = useReaction(edit)

  const loadFirstPage = useCallback(async () => {
    const ticket = ++generation.current
    const result = await loadCommunityFeed({ communityId: id })
    if (ticket !== generation.current) return
    if (result.ok) {
      cursor.current = result.value.nextCursor
      patch({ posts: result.value.posts, hasMore: result.value.nextCursor !== null, feedLoaded: true, feedFailed: false })
    } else {
      cursor.current = null
      patch({ feedLoaded: true, feedFailed: result.error !== 'forbidden', hasMore: false })
    }
  }, [id, loadCommunityFeed, patch])

  const load = useCallback(
    async (prompt: boolean) => {
      const location = await resolveLocation({ prompt })
      const here = location.ok ? location.value.cell : null
      setCell(here)
      const result = await loadCommunity({ id, cell: here })
      if (!result.ok) return patch({ loaded: true, failed: true, refreshing: false })
      patch({ loaded: true, failed: false, community: result.value, noLocation: here === null })
      if (result.value.isMember) await loadFirstPage()
      else patch({ posts: [], feedLoaded: true, hasMore: false })
    },
    [id, resolveLocation, loadCommunity, loadFirstPage, patch],
  )

  useEffect(() => {
    // load() only sets state after the first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(true)
  }, [load])

  const refresh = useCallback(async () => {
    patch({ refreshing: true })
    await load(false)
    patch({ refreshing: false })
  }, [load, patch])

  const loadMore = useCallback(async () => {
    if (!cursor.current || loadingMore.current) return
    loadingMore.current = true
    patch({ loadingMore: true })
    const ticket = generation.current
    const result = await loadCommunityFeed({ communityId: id, cursor: cursor.current })
    loadingMore.current = false
    if (ticket !== generation.current) return patch({ loadingMore: false })
    if (result.ok) {
      cursor.current = result.value.nextCursor
      const page = result.value.posts
      setState((s) => ({ ...s, posts: appendPage(s.posts, page), hasMore: result.value.nextCursor !== null, loadingMore: false }))
    } else {
      patch({ loadingMore: false })
    }
  }, [id, loadCommunityFeed, patch])

  const { community } = state
  const canJoin = !!community && !community.isMember && community.inRange && cell !== null

  const join = useCallback(
    async (pseudonym?: string) => {
      if (!community || !cell || joining) return
      setJoining(true)
      setJoinError(null)
      const result = await joinCommunity({ communityId: community.id, cell, pseudonym })
      setJoining(false)
      if (!result.ok) return setJoinError(result.error)
      setPromptOpen(false)
      setState((s) => (s.community ? { ...s, community: { ...s.community, isMember: true, memberCount: s.community.memberCount + 1 } } : s))
      await loadFirstPage()
    },
    [community, cell, joining, joinCommunity, loadFirstPage],
  )

  /** The Join button: asks for a pseudonym first when the community allows them. */
  const requestJoin = useCallback(async () => {
    if (!canJoin) return
    setJoinError(null)
    if (community.allowPseudonyms) setPromptOpen(true)
    else await join()
  }, [canJoin, community, join])

  const cancelPrompt = useCallback(() => {
    setPromptOpen(false)
    setJoinError(null)
  }, [])

  return { state, canJoin, promptOpen, joining, joinError, requestJoin, join, cancelPrompt, refresh, loadMore, react }
}
