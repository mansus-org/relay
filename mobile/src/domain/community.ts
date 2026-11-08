import type { LatLng } from './post'

export const MIN_RADIUS_KM = 1
export const MAX_RADIUS_KM = 50
export const DEFAULT_RADIUS_KM = 5
export const MAX_COMMUNITY_NAME_LENGTH = 80
export const MAX_PSEUDONYM_LENGTH = 40

export type CommunityDetails = {
  readonly id: string
  readonly name: string
  readonly description: string
  readonly memberCount: number
  /** H3 cell the community is anchored to, or null for a community with no location scope. */
  readonly locationCell: string | null
  readonly radiusKm: number | null
  readonly allowPseudonyms: boolean
  /** True when the signed-in user has joined. */
  readonly isMember: boolean
  readonly createdBy: { readonly id: string; readonly name: string } | null
  /** ISO 8601 timestamp. */
  readonly createdAt: string | null
}

/** A community as seen from the user's position. Both are null when the community has no location. */
export type NearbyCommunity = CommunityDetails & {
  readonly distanceKm: number | null
  readonly inRange: boolean
}

export type NewCommunity = {
  readonly name: string
  readonly description: string
  /** Leave out to create a community without a location scope. */
  readonly locationCell?: string
  readonly radiusKm: number
  readonly allowPseudonyms: boolean
}

export type JoinRequest = {
  readonly communityId: string
  /** The user's current H3 cell; the server checks it against the community's radius. */
  readonly cell: string
  readonly pseudonym?: string
}

export type CommunityFeedQuery = { readonly communityId: string; readonly cursor?: string }

export type CommunityError = ApiErrorLike | 'out-of-range' | 'forbidden'
type ApiErrorLike = 'network' | 'unexpected'

export type CreateCommunityError = ApiErrorLike | 'empty-name' | 'name-too-long' | 'bad-radius'

export const clampRadius = (km: number): number => Math.min(MAX_RADIUS_KM, Math.max(MIN_RADIUS_KM, Math.round(km)))

export const validateNewCommunity = (input: Pick<NewCommunity, 'name' | 'radiusKm'>): 'empty-name' | 'name-too-long' | 'bad-radius' | null => {
  if (input.name.trim() === '') return 'empty-name'
  if (input.name.trim().length > MAX_COMMUNITY_NAME_LENGTH) return 'name-too-long'
  if (!Number.isFinite(input.radiusKm) || input.radiusKm < MIN_RADIUS_KM || input.radiusKm > MAX_RADIUS_KM) return 'bad-radius'
  return null
}

const EARTH_RADIUS_KM = 6371

/** Great-circle distance in km (haversine). */
export const distanceKm = (a: LatLng, b: LatLng): number => {
  const rad = (deg: number) => (deg * Math.PI) / 180
  const dLat = rad(b.lat - a.lat)
  const dLng = rad(b.lng - a.lng)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** Places a community relative to `from`; `centerOf` turns its anchor cell into a coordinate. */
export const placeCommunity = (
  community: CommunityDetails,
  from: LatLng,
  centerOf: (cell: string) => LatLng,
): NearbyCommunity => {
  if (!community.locationCell) return { ...community, distanceKm: null, inRange: true }
  const distance = distanceKm(from, centerOf(community.locationCell))
  return { ...community, distanceKm: distance, inRange: community.radiusKm === null || distance <= community.radiusKm }
}

/** Nearest first; communities without a location go last, ties keep their order. */
export const sortByDistance = (communities: readonly NearbyCommunity[]): readonly NearbyCommunity[] =>
  communities
    .map((community, index) => ({ community, index }))
    .sort((a, b) => {
      const da = a.community.distanceKm ?? Infinity
      const db = b.community.distanceKm ?? Infinity
      return da === db ? a.index - b.index : da - db
    })
    .map(({ community }) => community)

/** "~2 km away"; under a kilometre reads "<1 km away". Null when there is no distance. */
export const formatDistance = (km: number | null): string | null => {
  if (km === null) return null
  return km < 1 ? '<1 km away' : `~${Math.round(km)} km away`
}

/** First `max` characters on a word boundary, with an ellipsis when cut. */
export const excerpt = (text: string, max = 100): string => {
  const flat = text.replace(/\s+/g, ' ').trim()
  if (flat.length <= max) return flat
  const cut = flat.slice(0, max)
  const space = cut.lastIndexOf(' ')
  return `${(space > max / 2 ? cut.slice(0, space) : cut).trimEnd()}…`
}
