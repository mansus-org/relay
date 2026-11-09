import { useCallback, useState } from 'react'

import { adminErrorMessage, type ModeratedPost } from '../domain'
import { useUseCases } from './use-cases'

export type QueueState = {
  /** False until the first read comes back. */
  loaded: boolean
  posts: readonly ModeratedPost[]
  /** Pulling the queue again by hand, or coming back to it. */
  refreshing: boolean
  /** Why the queue would not load. */
  problem: string | null
}

const initial: QueueState = { loaded: false, posts: [], refreshing: false, problem: null }

/**
 * The posts on this node that nobody has decided about, newest first.
 *
 * The screen asks for them on focus rather than this hook doing it on mount: a decision made on a
 * post's own page should be gone from this list the moment you are back looking at it. Nothing
 * else happens here. Approving and removing belong to the post, and the post has its own page.
 */
export function useAdminQueue() {
  const { loadQueue } = useUseCases()
  const [state, setState] = useState<QueueState>(initial)

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, refreshing: true, problem: null }))
    const result = await loadQueue()
    setState((s) => ({
      ...s,
      loaded: true,
      refreshing: false,
      posts: result.ok ? result.value : s.posts,
      problem: result.ok ? null : adminErrorMessage(result.error),
    }))
  }, [loadQueue])

  return { state, refresh }
}
