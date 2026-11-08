import { FEED_RADIUS_KM, type FeedPage, type FeedRepository, type ApiError, type Result } from '../domain'

export const makeLoadFeed =
  ({ feedRepository }: { feedRepository: FeedRepository }) =>
  (input: { cell: string; cursor?: string }): Promise<Result<FeedPage, ApiError>> =>
    feedRepository.list({ cell: input.cell, radiusKm: FEED_RADIUS_KM, cursor: input.cursor })
