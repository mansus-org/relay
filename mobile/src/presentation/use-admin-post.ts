import { useCallback, useEffect, useRef, useState } from 'react'

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

const initial: PostState = { loaded: false, post: null, busy: false, problem: null }

/**
 * What the node said back when asked to decide.
 *
 * `already` is not a failure to show and then leave up: another admin got there first, and the
 * post is still on screen saying it is waiting. The screen marks it dealt with and reads it again,
 * so what is left on screen is the truth.
 */
export type Decision = 'decided' | 'already' | 'refused'

/**
 * One post whole, and the two things an admin can do to it.
 *
 * It is read again here instead of being handed over from the queue, because the queue may be a
 * minute old and another admin may have decided in that minute. What is on screen is what the node
 * says now, and a post that has already been decided says so rather than offering the buttons again.
 *
 * The screen calls `load` when it comes into view, the same way the queue does: this page is reached
 * from the list, and it should be the node's answer that is on it, not the last one cached here.
 */
export function useAdminPost(id: string) {
  const { loadModeratedPost, reviewPost } = useUseCases()
  const [state, setState] = useState<PostState>(initial)
  const alive = useRef(true)
  const asked = useRef(false)

  const load = useCallback(async () => {
    alive.current = true
    // Whatever was on this page belongs to whatever was on it before. A read starts from a blank
    // page, so a post that is no longer the one being asked about never gets shown again.
    setState((s) => ({ ...s, loaded: false, post: null, problem: null }))
    const result = await loadModeratedPost({ id })
    if (!alive.current) return
    setState((s) => ({
      ...s,
      loaded: true,
      post: result.ok ? result.value : null,
      problem: result.ok ? null : adminErrorMessage(result.error),
    }))
  }, [id, loadModeratedPost])

  useEffect(() => () => void (alive.current = false), [])

  /**
   * Ask the node to approve or remove.
   *
   * The screen goes back to the queue on `decided`, so nothing here may still be running by the
   * time it does: every answer checks whether this page is still up before it says anything.
   */
  const decide = useCallback(
    async (action: ReviewAction, reason = ''): Promise<Decision> => {
      if (asked.current) return 'refused' // a second tap in the same beat, before busy reaches the button
      asked.current = true
      setState((s) => ({ ...s, busy: true, problem: null }))
      const result = await reviewPost({ id, action, reason })
      asked.current = false
      if (!alive.current) return 'refused'
      if (result.ok) {
        setState((s) => ({ ...s, busy: false, problem: null }))
        return 'decided'
      }
      if (result.error === 'already-decided') {
        // The page said "waiting" and that is now wrong. Read it again rather than leaving an
        // admin looking at a stamp the node has already overwritten.
        setState((s) => ({ ...s, busy: false, problem: null }))
        await load()
        return 'already'
      }
      setState((s) => ({ ...s, busy: false, problem: adminErrorMessage(result.error) }))
      return 'refused'
    },
    [id, load, reviewPost],
  )

  return { state, load, decide }
}
