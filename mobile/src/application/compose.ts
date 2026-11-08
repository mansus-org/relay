import {
  err,
  validatePostBody,
  type ApiError,
  type Community,
  type CommunityRepository,
  type ComposeError,
  type Post,
  type PostRepository,
  type Result,
} from '../domain'

export type CreatePostInput = {
  readonly body: string
  /** Leave out to post without a location. */
  readonly locationCell?: string
  readonly communityId?: string
}

export const makeCreatePost =
  ({ postRepository }: { postRepository: PostRepository }) =>
  async ({ body, locationCell, communityId }: CreatePostInput): Promise<Result<Post, ComposeError>> => {
    const invalid = validatePostBody(body)
    if (invalid) return err(invalid)
    return postRepository.create({ body: body.trim(), locationCell, communityId })
  }

export const makeListJoinedCommunities =
  ({ communityRepository }: { communityRepository: CommunityRepository }) =>
  (): Promise<Result<readonly Community[], ApiError>> =>
    communityRepository.listJoined()
