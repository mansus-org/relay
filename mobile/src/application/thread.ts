import {
  err,
  validatePostBody,
  type ApiError,
  type ComposeError,
  type Post,
  type PostRepository,
  type Result,
} from '../domain'

/** The post that starts a thread, which is what the thread screen opens on. */
export const makeLoadThread =
  ({ postRepository }: { postRepository: PostRepository }) =>
  (postId: string): Promise<Result<Post, ApiError>> => postRepository.get(postId)

/** One level of what was said under a post, oldest first. */
export const makeLoadReplies =
  ({ postRepository }: { postRepository: PostRepository }) =>
  (postId: string): Promise<Result<readonly Post[], ApiError>> => postRepository.listReplies(postId)

export type ReplyInput = {
  readonly parentId: string
  readonly body: string
}

/**
 * Answers a post. A reply is said where the post it answers was said, so it carries no
 * location of its own; the server takes the one its parent has.
 */
export const makeReply =
  ({ postRepository }: { postRepository: PostRepository }) =>
  async ({ parentId, body }: ReplyInput): Promise<Result<Post, ComposeError>> => {
    const invalid = validatePostBody(body)
    if (invalid) return err(invalid)
    return postRepository.create({ body: body.trim(), parentId })
  }
