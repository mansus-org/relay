import {
  myReaction,
  type ApiError,
  type Post,
  type PostRepository,
  type Reaction,
  type Result,
  ok,
} from '../domain'

/**
 * Toggles one emoji on a post and answers what that emoji now counts.
 *
 * Taking one back answers zero because a 204 says nothing else, and the client has
 * already moved its own count by the time this returns.
 */
export const makeToggleReaction =
  ({ postRepository }: { postRepository: PostRepository }) =>
  async (post: Post, emoji: string): Promise<Result<Reaction, ApiError>> => {
    if (!myReaction(post, emoji)) return postRepository.react(post.id, emoji)
    const removed = await postRepository.unreact(post.id, emoji)
    return removed.ok ? ok({ emoji, count: 0, mine: false }) : removed
  }
