import type { AxiosInstance } from 'axios'

import {
  err,
  ok,
  type AdminMember,
  type MemberRepository,
  type ModerationLogEntry,
} from '../../domain'
import { toAdminError } from './api-error'
import { ADMIN_MEMBERS_PATH, adminMemberPath } from './endpoints'

/** How many accounts to ask for at a time. The node answers 50 when asked for nothing. */
const PAGE = 50

export type MemberDto = {
  id: number
  username: string
  display_name: string
  is_admin: boolean
  created_at: string
  deactivated_at?: string | null
  is_deactivated: boolean
}

export type LogEntryDto = {
  id: number
  actor_id: number | null
  action: string
  trigger: string
  post_id?: string | null
  community_id?: string | null
  target_user_id?: number | null
  reason: string
  created_at: string
}

export const toMember = (dto: MemberDto): AdminMember => ({
  id: dto.id,
  name: dto.display_name,
  handle: dto.username,
  joinedAt: dto.created_at,
  isAdmin: dto.is_admin,
  deactivatedAt: dto.deactivated_at ?? null,
})

export const toLogEntry = (dto: LogEntryDto): ModerationLogEntry => ({
  id: dto.id,
  action: dto.action,
  trigger: dto.trigger,
  reason: dto.reason,
  createdAt: dto.created_at,
  postId: dto.post_id ?? null,
  targetUserId: dto.target_user_id ?? null,
})

export const makeHttpMemberRepository = ({ http }: { http: AxiosInstance }): MemberRepository => ({
  async list(from = 0) {
    try {
      const { data } = await http.get<{ members?: MemberDto[] }>(ADMIN_MEMBERS_PATH, {
        params: { limit: PAGE, offset: from },
      })
      return ok((data.members ?? []).map(toMember))
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async detail(id) {
    try {
      const { data } = await http.get<{ member: MemberDto; history?: LogEntryDto[] }>(adminMemberPath(id))
      return ok({ member: toMember(data.member), history: (data.history ?? []).map(toLogEntry) })
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async remove(id, reason) {
    try {
      // The reason goes in the query, where the node looks for it, and it has to say something.
      const { data } = await http.delete<{ sessions_ended?: number }>(adminMemberPath(id), { params: { reason } })
      return ok<number>(data.sessions_ended ?? 0)
    } catch (error) {
      return err(toAdminError(error))
    }
  },
})
