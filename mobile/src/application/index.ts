import type { SessionEvents } from '../domain'
import type { makeCreatePost, makeListJoinedCommunities } from './compose'
import type { makeLoadFeed } from './feed'
import type { makeCellPlaceName, makeResolveLocation } from './resolve-location'
import type { makeSubscribeToPosts } from './subscribe-to-posts'
import type { makeLogin } from './login'
import type { makeRegister } from './register'
import type { makeLogout } from './logout'
import type { makeRestoreSession } from './restore-session'

export { makeCreatePost, makeListJoinedCommunities, type CreatePostInput } from './compose'
export { makeLoadFeed } from './feed'
export { makeCellPlaceName, makeResolveLocation, type LocationError, type ResolvedLocation } from './resolve-location'
export { makeSubscribeToPosts } from './subscribe-to-posts'
export { makeLogin, type LoginInput } from './login'
export { makeLogout } from './logout'
export { makeRegister, type RegisterInput } from './register'
export { makeRefreshSession } from './refresh-session'
export { makeRestoreSession } from './restore-session'

/** Everything the presentation layer may call; built once by the composition root. */
export type UseCases = {
  readonly login: ReturnType<typeof makeLogin>
  readonly register: ReturnType<typeof makeRegister>
  readonly logout: ReturnType<typeof makeLogout>
  readonly restoreSession: ReturnType<typeof makeRestoreSession>
  readonly loadFeed: ReturnType<typeof makeLoadFeed>
  readonly resolveLocation: ReturnType<typeof makeResolveLocation>
  readonly placeNameOf: ReturnType<typeof makeCellPlaceName>
  readonly subscribeToPosts: ReturnType<typeof makeSubscribeToPosts>
  readonly createPost: ReturnType<typeof makeCreatePost>
  readonly listJoinedCommunities: ReturnType<typeof makeListJoinedCommunities>
  readonly sessionEvents: SessionEvents
}
