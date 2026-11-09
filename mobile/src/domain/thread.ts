import type { Post } from './post'

/** Replies deeper than this are drawn at this depth: a thread that deep stops getting narrower. */
export const MAX_THREAD_DEPTH = 3

/** One post on screen in a thread, with how far it sits from the post that started it. */
export type ThreadEntry = {
  readonly post: Post
  readonly depth: number
  /** True while this post's own replies are on screen. */
  readonly open: boolean
}

/** A thread with nothing said under it yet. */
export const threadOf = (post: Post): readonly ThreadEntry[] => [{ post, depth: 0, open: false }]

/** The entry that follows this post's replies, which is the first one no longer indented under it. */
const endUnder = (entries: readonly ThreadEntry[], at: number): number => {
  let end = at + 1
  while (end < entries.length && entries[end]!.depth > entries[at]!.depth) end++
  return end
}

const under = (entries: readonly ThreadEntry[], postId: string): readonly [number, number] | null => {
  const at = entries.findIndex((e) => e.post.id === postId)
  return at === -1 ? null : [at, endUnder(entries, at)]
}

/** Puts one level of replies under the post they answer and marks it open; old ones are replaced. */
export const insertReplies = (
  entries: readonly ThreadEntry[],
  postId: string,
  replies: readonly Post[],
): readonly ThreadEntry[] => {
  const found = under(entries, postId)
  if (!found) return entries
  const [at, end] = found
  const depth = Math.min(entries[at]!.depth + 1, MAX_THREAD_DEPTH)
  const opened = { ...entries[at]!, open: replies.length > 0 }
  return [...entries.slice(0, at), opened, ...replies.map((post) => ({ post, depth, open: false })), ...entries.slice(end)]
}

/** Takes a post's replies off the screen again, so "show replies" can ask for them another time. */
export const dropReplies = (entries: readonly ThreadEntry[], postId: string): readonly ThreadEntry[] => {
  const found = under(entries, postId)
  if (!found) return entries
  const [at, end] = found
  return [...entries.slice(0, at), { ...entries[at]!, open: false }, ...entries.slice(end)]
}

/** Adds a reply under the post it answers, after everything already shown there, and opens it. */
export const appendReply = (entries: readonly ThreadEntry[], postId: string, reply: Post): readonly ThreadEntry[] => {
  const found = under(entries, postId)
  if (!found) return entries
  const [at, end] = found
  const depth = Math.min(entries[at]!.depth + 1, MAX_THREAD_DEPTH)
  const opened = { ...entries[at]!, open: true }
  return [
    ...entries.slice(0, at),
    opened,
    ...entries.slice(at + 1, end),
    { post: reply, depth, open: false },
    ...entries.slice(end),
  ]
}

/** Puts a post in place of the one on screen with the id given, which is how a reply sent off its placeholder. */
export const replacePost = (entries: readonly ThreadEntry[], postId: string, post: Post): readonly ThreadEntry[] =>
  entries.map((e) => (e.post.id === postId ? { ...e, post } : e))

/** Takes a post out of the thread, and everything said under it with it. */
export const removeEntry = (entries: readonly ThreadEntry[], postId: string): readonly ThreadEntry[] => {
  const found = under(entries, postId)
  if (!found) return entries
  const [at, end] = found
  return [...entries.slice(0, at), ...entries.slice(end)]
}
