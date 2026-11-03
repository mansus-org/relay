import type { AxiosInstance } from 'axios'

import { err, ok, type CommunityDetails, type CommunityError, type CommunityRepository } from '../../domain'
import { toApiError, statusOf } from './api-error'
import { COMMUNITIES_PATH, JOINED_COMMUNITIES_PATH, communityFeedPath, communityJoinPath, communityPath } from './endpoints'
import { toPost, type PostDto } from './post-dto'

export type CommunityDto = {
  id: string
  name: string
  description?: string | null
  member_count?: number
  location_cell?: string | null
  radius_km?: number | null
  allow_pseudonyms?: boolean
  is_member?: boolean
  created_by?: { id: string; name: string } | null
  created_at?: string | null
}

export const toCommunity = (dto: CommunityDto): CommunityDetails => ({
  id: dto.id,
  name: dto.name,
  description: dto.description ?? '',
  memberCount: dto.member_count ?? 0,
  locationCell: dto.location_cell ?? null,
  radiusKm: dto.radius_km ?? null,
  allowPseudonyms: dto.allow_pseudonyms ?? false,
  isMember: dto.is_member ?? false,
  createdBy: dto.created_by ? { id: dto.created_by.id, name: dto.created_by.name } : null,
  createdAt: dto.created_at ?? null,
})

const toCommunityError = (error: unknown, forbidden: CommunityError): CommunityError =>
  statusOf(error) === 403 ? forbidden : toApiError(error)

export const makeHttpCommunityRepository = ({ http }: { http: AxiosInstance }): CommunityRepository => ({
  async listJoined() {
    try {
      const { data } = await http.get<{ communities: { id: string; name: string }[] }>(JOINED_COMMUNITIES_PATH)
      return ok(data.communities.map(({ id, name }) => ({ id, name })))
    } catch (error) {
      // The endpoint is not deployed everywhere yet: a missing route means "no communities".
      if (statusOf(error) === 404) return ok([])
      return err(toApiError(error))
    }
  },

  async listNearby(cell) {
    try {
      // RELY-89 documents a bare array; an envelope like the joined endpoint's is accepted too.
      const { data } = await http.get<CommunityDto[] | { communities: CommunityDto[] }>(COMMUNITIES_PATH, { params: { cell } })
      return ok((Array.isArray(data) ? data : data.communities).map(toCommunity))
    } catch (error) {
      return err(toApiError(error))
    }
  },

  async get(id) {
    try {
      const { data } = await http.get<CommunityDto>(communityPath(id))
      return ok(toCommunity(data))
    } catch (error) {
      return err(toCommunityError(error, 'forbidden'))
    }
  },

  async join({ communityId, cell, pseudonym }) {
    try {
      // RELY-89: the server checks `cell` against the community's radius and answers 403 when outside.
      await http.post(communityJoinPath(communityId), { cell, ...(pseudonym ? { pseudonym } : {}) })
      return ok(undefined)
    } catch (error) {
      return err(toCommunityError(error, 'out-of-range'))
    }
  },

  async create({ name, description, locationCell, radiusKm, allowPseudonyms }) {
    try {
      // location_cell is omitted, not null, for a community without a location.
      const payload = {
        name,
        description,
        radius_km: radiusKm,
        allow_pseudonyms: allowPseudonyms,
        ...(locationCell ? { location_cell: locationCell } : {}),
      }
      const { data } = await http.post<CommunityDto>(COMMUNITIES_PATH, payload)
      return ok(toCommunity(data))
    } catch (error) {
      return err(toApiError(error))
    }
  },

  async feed({ communityId, cursor }) {
    try {
      const { data } = await http.get<{ posts: PostDto[]; next_cursor?: string | null }>(communityFeedPath(communityId), {
        params: { cursor },
      })
      return ok({ posts: data.posts.map(toPost), nextCursor: data.next_cursor ?? null })
    } catch (error) {
      return err(toCommunityError(error, 'forbidden'))
    }
  },
})
