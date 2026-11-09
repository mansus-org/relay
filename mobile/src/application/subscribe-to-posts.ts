import type { StreamEvent, PostStream } from '../domain'

export const makeSubscribeToPosts =
  ({ postStream }: { postStream: PostStream }) =>
  (cell: string, onEvent: (event: StreamEvent) => void): (() => void) =>
    postStream.subscribe(cell, onEvent)
