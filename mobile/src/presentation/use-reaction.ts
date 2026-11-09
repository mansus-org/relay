import { useCallback } from 'react'

import { mergeReaction, myReaction, toggleReaction as toggleOnPost, type Post, type Reaction } from '../domain'
import { useUseCases } from './use-cases'

/** Puts a reaction on a list of posts already on screen, however that list is held. */
export type EditPost = (postId: string, next: (post: Post) => Post) => void

/**
 * Sends a reaction for a list of posts, without waiting for the server to answer.
 *
 * The tap goes on the screen at once and the server's own tally replaces it when it answers; if it
 * refuses, the tap is taken back. `edit` says how to change a post in the list this hook drives, so
 * the feed, a community's feed and a thread all react the same way with their own state.
 */
export function useReaction(edit: EditPost) {
  const { toggleReaction } = useUseCases()
  return useCallback(
    async (post: Post, emoji: string): Promise<void> => {
      const back: Reaction = myReaction(post, emoji) ?? { emoji, count: 0, mine: false }
      edit(post.id, (p) => toggleOnPost(p, emoji))
      const result = await toggleReaction(post, emoji)
      edit(post.id, (p) => ({ ...p, reactions: mergeReaction(p.reactions, result.ok ? result.value : back) }))
    },
    [edit, toggleReaction],
  )
}
