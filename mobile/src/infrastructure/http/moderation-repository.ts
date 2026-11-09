import type { AxiosInstance } from 'axios'

import {
  err,
  ok,
  type ModeratedPost,
  type ModerationDecision,
  type ModerationRepository,
} from '../../domain'
import { toAdminError } from './api-error'
import { ADMIN_QUEUE_PATH, adminPostPath, adminReviewPath } from './endpoints'

export type ModeratedPostDto = {
  id: string
  author_id: string
  body: string
  created_at: string
  moderation_status: string
  community_id?: string | null
  parent_id?: string | null
  /** Whatever the model that looked at this post chose to call things. Null when none ever did. */
  ai_decision?: Record<string, unknown> | null
}

/** Anything the node has not heard of counts as still waiting, rather than silently vanishing. */
const toStatus = (value: string): ModerationDecision => (value === 'approved' || value === 'removed' ? value : 'pending')

export const toModeratedPost = (dto: ModeratedPostDto): ModeratedPost => ({
  id: dto.id,
  body: dto.body,
  createdAt: dto.created_at,
  authorId: dto.author_id,
  status: toStatus(dto.moderation_status),
  communityId: dto.community_id ?? null,
  parentId: dto.parent_id ?? null,
  ai: dto.ai_decision ?? null,
})

export const makeHttpModerationRepository = ({ http }: { http: AxiosInstance }): ModerationRepository => ({
  async queue() {
    try {
      const { data } = await http.get<{ posts?: ModeratedPostDto[] }>(ADMIN_QUEUE_PATH)
      return ok((data.posts ?? []).map(toModeratedPost))
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async get(postId) {
    try {
      const { data } = await http.get<ModeratedPostDto>(adminPostPath(postId))
      return ok(toModeratedPost(data))
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async review(postId, action, reason) {
    try {
      // A removal without a reason is refused before the node looks at the post, so the screen asks first.
      const { data } = await http.post<ModeratedPostDto>(adminReviewPath(postId, action), { reason })
      return ok(toStatus(data.moderation_status))
    } catch (error) {
      return err(toAdminError(error))
    }
  },
})
