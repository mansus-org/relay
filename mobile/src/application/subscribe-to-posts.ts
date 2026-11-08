import type { Post, PostStream } from '../domain'

export const makeSubscribeToPosts =
  ({ postStream }: { postStream: PostStream }) =>
  (cell: string, onPost: (post: Post) => void): (() => void) =>
    postStream.subscribe(cell, onPost)
