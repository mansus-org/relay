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
 * Posts decided on their own page, remembered between screens.
 *
 * A decision is made a screen away from this list, and the node has already taken it by the time
 * you are back looking at the queue. Reading the list again takes a round trip; a post you have
 * just dealt with should not sit there for the length of it. Nothing is *removed* from here - the
 * fresh list from the node is the truth, and this only says which ones you already know the answer
 * to.
 *
 * It sits at module scope because the page that decides is not the page that lists. That also makes
 * it shared by every queue on the app stack, which is why `refresh` throws it away as soon as the
 * node answers: a memory is worth less than the list it was written against.
 */
const decided = new Set<string>()

/** Call this the moment the node agrees a post is dealt with, before going back to the queue. */
export function markDecided(id: string): void {
  decided.add(id)
}

/**
 * The posts on this node that nobody has decided about, newest first.
 *
 * The screen asks for them on focus rather than this hook doing it on mount: a decision made on a
 * post's own page should be gone from this list the moment you are back looking at it. Nothing
 * else happens here. Approving and removing belong to the post, and the post has its own page -
 * it only tells this one which posts it no longer needs to show.
 */
export function useAdminQueue() {
  const { loadQueue } = useUseCases()
  const [state, setState] = useState<QueueState>(initial)

  const refresh = useCallback(async () => {
    setState((s) => ({
      ...s,
      refreshing: true,
      problem: null,
      posts: s.posts.filter((p) => !decided.has(p.id)),
    }))
    const result = await loadQueue()
    // Whatever was remembered is now worth less than nothing: the node has answered, and its list
    // is the truth from here. Keeping the memory would hide a post the node still thinks is
    // waiting, on this node or whichever one is connected next.
    decided.clear()
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
