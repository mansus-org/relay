import type { User } from './user'

export const MAX_POST_LENGTH = 500
export const FEED_RADIUS_KM = 10

export type Reaction = {
  readonly emoji: string
  readonly count: number
  /** True when the signed-in user has reacted with this emoji. */
  readonly mine: boolean
}

export type Post = {
  readonly id: string
  readonly author: User
  readonly body: string
  /** ISO 8601 timestamp. */
  readonly createdAt: string
  /** H3 cell of the post, or null for posts private to node members. */
  readonly locationCell: string | null
  readonly reactions: readonly Reaction[]
  readonly replyCount: number
}

export type FeedPage = {
  readonly posts: readonly Post[]
  /** Null on the last page. */
  readonly nextCursor: string | null
}

export type FeedQuery = {
  readonly cell: string
  readonly radiusKm: number
  readonly cursor?: string
}

export type NewPost = {
  readonly body: string
  readonly locationCell?: string
  readonly communityId?: string
}

export type Community = {
  readonly id: string
  readonly name: string
}

export type ApiError = 'network' | 'unexpected'

export type ComposeError = ApiError | 'empty' | 'too-long'

export type LatLng = { readonly lat: number; readonly lng: number }

export type LocationStatus = { readonly granted: boolean; readonly canAskAgain: boolean }

/** Appends an older page, skipping posts already in the list. */
export const appendPage = (current: readonly Post[], page: readonly Post[]): readonly Post[] => {
  const seen = new Set(current.map((p) => p.id))
  return [...current, ...page.filter((p) => !seen.has(p.id))]
}

/** Puts incoming posts (newest first) in front of the list, skipping ones it already has. */
export const prependPosts = (current: readonly Post[], incoming: readonly Post[]): readonly Post[] => {
  const seen = new Set(current.map((p) => p.id))
  return [...incoming.filter((p) => !seen.has(p.id)), ...current]
}

/** Adds a streamed post to a buffer of unseen posts, newest first, without duplicates. */
export const bufferPost = (buffer: readonly Post[], post: Post): readonly Post[] =>
  buffer.some((p) => p.id === post.id) ? buffer : [post, ...buffer]

export const charsLeft = (body: string): number => MAX_POST_LENGTH - body.length

export const validatePostBody = (body: string): 'empty' | 'too-long' | null => {
  if (body.trim() === '') return 'empty'
  return body.length > MAX_POST_LENGTH ? 'too-long' : null
}

/** "just now", "5 min ago", "1 h ago", "3 d ago"; older than a month falls back to the date. */
export const timeAgo = (iso: string, now: Date): string => {
  const seconds = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 1000))
  if (Number.isNaN(seconds)) return ''
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} d ago`
  return iso.slice(0, 10)
}
