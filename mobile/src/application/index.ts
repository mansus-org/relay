import type { SessionEvents } from '../domain'
import type { makeCreateCommunity, makeJoinCommunity, makeLoadCommunity, makeLoadCommunityFeed, makeLoadNearbyCommunities } from './communities'
import type {
  makeCancelRsvp,
  makeCreateEvent,
  makeLoadEvent,
  makeLoadNearbyEvents,
  makeRsvpToEvent,
} from './events'
import type { makeCreatePost, makeListJoinedCommunities } from './compose'
import type { makeLoadFeed } from './feed'
import type { makeCellPlaceName, makeResolveLocation } from './resolve-location'
import type { makeReadPostalCode, makeResolvePostalCode } from './resolve-postal-code'
import type { makeSubscribeToPosts } from './subscribe-to-posts'
import type { makeLogin } from './login'
import type { makeRegister } from './register'
import type { makeLogout } from './logout'
import type { makeRestoreSession } from './restore-session'

export {
  makeCreateCommunity,
  makeJoinCommunity,
  makeLoadCommunity,
  makeLoadCommunityFeed,
  makeLoadNearbyCommunities,
  type CreateCommunityInput,
  type JoinCommunityInput,
} from './communities'
export { makeCreatePost, makeListJoinedCommunities, type CreatePostInput } from './compose'
export {
  makeCancelRsvp,
  makeCreateEvent,
  makeLoadEvent,
  makeLoadNearbyEvents,
  makeRsvpToEvent,
  type DetailedEvent,
} from './events'
export { makeLoadFeed } from './feed'
export { makeCellPlaceName, makeResolveLocation, type LocationError, type ResolvedLocation } from './resolve-location'
export { makeReadPostalCode, makeResolvePostalCode } from './resolve-postal-code'
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
  /** The place a typed postal code names, or why Relay has no place there. */
  readonly resolvePostalCode: ReturnType<typeof makeResolvePostalCode>
  /** The code to open the feed on, before anything is on screen. */
  readonly readPostalCode: ReturnType<typeof makeReadPostalCode>
  readonly placeNameOf: ReturnType<typeof makeCellPlaceName>
  readonly subscribeToPosts: ReturnType<typeof makeSubscribeToPosts>
  readonly createPost: ReturnType<typeof makeCreatePost>
  readonly listJoinedCommunities: ReturnType<typeof makeListJoinedCommunities>
  readonly loadNearbyCommunities: ReturnType<typeof makeLoadNearbyCommunities>
  readonly loadCommunity: ReturnType<typeof makeLoadCommunity>
  readonly loadCommunityFeed: ReturnType<typeof makeLoadCommunityFeed>
  readonly joinCommunity: ReturnType<typeof makeJoinCommunity>
  readonly createCommunity: ReturnType<typeof makeCreateCommunity>
  readonly loadNearbyEvents: ReturnType<typeof makeLoadNearbyEvents>
  readonly loadEvent: ReturnType<typeof makeLoadEvent>
  readonly rsvpToEvent: ReturnType<typeof makeRsvpToEvent>
  readonly cancelRsvp: ReturnType<typeof makeCancelRsvp>
  readonly createEvent: ReturnType<typeof makeCreateEvent>
  readonly sessionEvents: SessionEvents
}
