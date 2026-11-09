import { useCallback, useEffect, useState } from 'react'

import { adminErrorMessage, type ModeratedPost, type ReviewAction } from '../domain'
import { useUseCases } from './use-cases'

type PostState = {
  /** False until the post has been read. */
  loaded: boolean
  /** Null when there is no such post on this node. */
  post: ModeratedPost | null
  /** The decision is on its way to the node. */
  busy: boolean
  problem: string | null
}

/**
 * One post whole, and the two things an admin can do to it.
 *
 * It is read again here instead of being handed over from the queue, because the queue may be a
 * minute old and another admin may have decided in that minute. What is on screen is what the node
 * says now, and a post that has already been decided says so rather than offering the buttons again.
 */
export function useAdminPost(id: string) {
  const { loadModeratedPost, reviewPost } = useUseCases()
  const [state, setState] = useState<PostState>({ loaded: false, post: null, busy: false, problem: null })

  useEffect(() => {
    let gone = false
    void loadModeratedPost({ id }).then((result) => {
      if (gone) return
      setState((s) => ({
        ...s,
        loaded: true,
        post: result.ok ? result.value : null,
        problem: result.ok ? null : adminErrorMessage(result.error),
      }))
    })
    return () => {
      gone = true
    }
  }, [id, loadModeratedPost])

  /** True when the node took the decision. The screen goes back to the queue on that. */
  const decide = useCallback(
    async (action: ReviewAction, reason = '') => {
      setState((s) => ({ ...s, busy: true, problem: null }))
      const result = await reviewPost({ id, action, reason })
      setState((s) => ({ ...s, busy: false, problem: result.ok ? null : adminErrorMessage(result.error) }))
      return result.ok
    },
    [id, reviewPost],
  )

  return { state, decide }
}
