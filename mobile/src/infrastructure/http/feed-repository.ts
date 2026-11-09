import type { AxiosInstance } from 'axios'

import { err, ok, type FeedRepository, type PostRepository } from '../../domain'
import { FEED_PATH, POSTS_PATH, postPath, postReactionsPath, postRepliesPath, reactionPath } from './endpoints'
import { toApiError } from './api-error'
import { toPost, type PostDto } from './post-dto'

type FeedDto = { posts: PostDto[]; next_cursor?: string | null }
type RepliesDto = { posts: PostDto[] }
type ReactionDto = { emoji: string; count: number; mine?: boolean }


export const makeHttpFeedRepository = ({ http }: { http: AxiosInstance }): FeedRepository => ({
  async list({ cell, radiusKm, cursor }) {
    try {
      const { data } = await http.get<FeedDto>(FEED_PATH, { params: { cell, radius: radiusKm, cursor } })
      return ok({ posts: data.posts.map(toPost), nextCursor: data.next_cursor ?? null })
    } catch (error) {
      return err(toApiError(error))
    }
  },
})

export const makeHttpPostRepository = ({ http }: { http: AxiosInstance }): PostRepository => ({
  async create({ body, locationCell, communityId, parentId }) {
    try {
      // location_cell, community_id and parent_id are omitted, not null, when not set.
      const payload = {
        body,
        ...(locationCell ? { location_cell: locationCell } : {}),
        ...(communityId ? { community_id: communityId } : {}),
        ...(parentId ? { parent_id: parentId } : {}),
      }
      const { data } = await http.post<PostDto>(POSTS_PATH, payload)
      return ok(toPost(data))
    } catch (error) {
      return err(toApiError(error))
    }
  },
  async get(id) {
    try {
      const { data } = await http.get<PostDto>(postPath(id))
      return ok(toPost(data))
    } catch (error) {
      return err(toApiError(error))
    }
  },
  async listReplies(id) {
    try {
      const { data } = await http.get<RepliesDto>(postRepliesPath(id))
      return ok(data.posts.map(toPost))
    } catch (error) {
      return err(toApiError(error))
    }
  },
  async react(id, emoji) {
    try {
      // The server answers with what that emoji now counts, so the client never guesses.
      const { data } = await http.post<ReactionDto>(postReactionsPath(id), { emoji })
      return ok({ emoji: data.emoji, count: data.count, mine: data.mine ?? true })
    } catch (error) {
      return err(toApiError(error))
    }
  },
  async unreact(id, emoji) {
    try {
      await http.delete(reactionPath(id, emoji))
      return ok(undefined)
    } catch (error) {
      return err(toApiError(error))
    }
  },
})
