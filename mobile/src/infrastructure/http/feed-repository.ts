import { AxiosError, type AxiosInstance } from 'axios'

import { err, ok, type ApiError, type CommunityRepository, type FeedRepository, type PostRepository } from '../../domain'
import { FEED_PATH, JOINED_COMMUNITIES_PATH, POSTS_PATH } from './endpoints'
import { toPost, type PostDto } from './post-dto'

type FeedDto = { posts: PostDto[]; next_cursor?: string | null }

const toApiError = (error: unknown): ApiError =>
  error instanceof AxiosError && !error.response ? 'network' : 'unexpected'

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
  async create({ body, locationCell, communityId }) {
    try {
      // location_cell and community_id are omitted, not null, when not set.
      const payload = {
        body,
        ...(locationCell ? { location_cell: locationCell } : {}),
        ...(communityId ? { community_id: communityId } : {}),
      }
      const { data } = await http.post<PostDto>(POSTS_PATH, payload)
      return ok(toPost(data))
    } catch (error) {
      return err(toApiError(error))
    }
  },
})

export const makeHttpCommunityRepository = ({ http }: { http: AxiosInstance }): CommunityRepository => ({
  async listJoined() {
    try {
      const { data } = await http.get<{ communities: { id: string; name: string }[] }>(JOINED_COMMUNITIES_PATH)
      return ok(data.communities.map(({ id, name }) => ({ id, name })))
    } catch (error) {
      // The endpoint is not deployed everywhere yet: a missing route means "no communities".
      if (error instanceof AxiosError && error.response?.status === 404) return ok([])
      return err(toApiError(error))
    }
  },
})
