import type { AxiosInstance } from 'axios'

import { err, ok, type Invite, type InviteRepository, type InviteState } from '../../domain'
import { toAdminError } from './api-error'
import { ADMIN_INVITES_PATH, adminInvitePath } from './endpoints'

/** How many invites to ask for at a time. */
const PAGE = 50

export type InviteDto = {
  id: number
  token: string
  url?: string | null
  note?: string | null
  state: string
  created_at?: string | null
  used_at?: string | null
  used_by_id?: number | null
  revoked_at?: string | null
}

/** An invite in a state this app has not heard of is treated as spent: it cannot be sent again. */
const toState = (value: string): InviteState => (value === 'open' || value === 'used' ? value : 'revoked')

export const toInvite = (dto: InviteDto): Invite => ({
  id: dto.id,
  token: dto.token,
  url: dto.url ?? null,
  note: dto.note ?? null,
  state: toState(dto.state),
  createdAt: dto.created_at ?? null,
  usedAt: dto.used_at ?? null,
  usedById: dto.used_by_id ?? null,
  revokedAt: dto.revoked_at ?? null,
})

export const makeHttpInviteRepository = ({ http }: { http: AxiosInstance }): InviteRepository => ({
  async list(from = 0) {
    try {
      // Every state, not just the open ones: a used invite is the answer to "who let that person in".
      const { data } = await http.get<{ invites?: InviteDto[] }>(ADMIN_INVITES_PATH, {
        params: { limit: PAGE, offset: from },
      })
      return ok((data.invites ?? []).map(toInvite))
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async issue(note) {
    try {
      const { data } = await http.post<InviteDto>(ADMIN_INVITES_PATH, { note })
      return ok(toInvite(data))
    } catch (error) {
      return err(toAdminError(error))
    }
  },

  async revoke(id) {
    try {
      const { data } = await http.delete<InviteDto>(adminInvitePath(id))
      return ok(toInvite(data))
    } catch (error) {
      return err(toAdminError(error))
    }
  },
})
