import {
  err,
  ok,
  placeCommunity,
  sortByDistance,
  validateNewCommunity,
  type ApiError,
  type CellEncoder,
  type CommunityDetails,
  type CommunityError,
  type CommunityRepository,
  type CreateCommunityError,
  type FeedPage,
  type NearbyCommunity,
  type Result,
} from '../domain'

type Deps = { readonly communityRepository: CommunityRepository }
type PlacingDeps = Deps & { readonly cellEncoder: CellEncoder }

/** Communities near the cell, nearest first, each flagged in or out of range of that cell. */
export const makeLoadNearbyCommunities =
  ({ communityRepository, cellEncoder }: PlacingDeps) =>
  async ({ cell }: { cell: string }): Promise<Result<readonly NearbyCommunity[], ApiError>> => {
    const result = await communityRepository.listNearby(cell)
    if (!result.ok) return result
    const from = cellEncoder.centerOf(cell)
    return ok(sortByDistance(result.value.map((c) => placeCommunity(c, from, cellEncoder.centerOf))))
  }

/** One community; without a cell its distance is unknown and it counts as out of range. */
export const makeLoadCommunity =
  ({ communityRepository, cellEncoder }: PlacingDeps) =>
  async ({ id, cell }: { id: string; cell: string | null }): Promise<Result<NearbyCommunity, CommunityError>> => {
    const result = await communityRepository.get(id)
    if (!result.ok) return result
    if (!cell) return ok({ ...result.value, distanceKm: null, inRange: false })
    return ok(placeCommunity(result.value, cellEncoder.centerOf(cell), cellEncoder.centerOf))
  }

export type JoinCommunityInput = {
  readonly communityId: string
  readonly cell: string
  /** Only sent when the community allows pseudonyms and this is not blank. */
  readonly pseudonym?: string
}

export const makeJoinCommunity =
  ({ communityRepository }: Deps) =>
  ({ communityId, cell, pseudonym }: JoinCommunityInput): Promise<Result<void, CommunityError>> => {
    const name = pseudonym?.trim()
    return communityRepository.join({ communityId, cell, ...(name ? { pseudonym: name } : {}) })
  }

export type CreateCommunityInput = {
  readonly name: string
  readonly description: string
  /** Leave out to create a community without a location scope. */
  readonly locationCell?: string
  readonly radiusKm: number
  readonly allowPseudonyms: boolean
}

export const makeCreateCommunity =
  ({ communityRepository }: Deps) =>
  async (input: CreateCommunityInput): Promise<Result<CommunityDetails, CreateCommunityError>> => {
    const invalid = validateNewCommunity(input)
    if (invalid) return err(invalid)
    return communityRepository.create({ ...input, name: input.name.trim(), description: input.description.trim() })
  }

export const makeLoadCommunityFeed =
  ({ communityRepository }: Deps) =>
  (input: { communityId: string; cursor?: string }): Promise<Result<FeedPage, CommunityError>> =>
    communityRepository.feed(input)
