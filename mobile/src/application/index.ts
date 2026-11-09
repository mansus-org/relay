import type { SessionEvents } from '../domain'
import type { makeCreateCommunity, makeJoinCommunity, makeLoadCommunity, makeLoadCommunityFeed, makeLoadNearbyCommunities } from './communities'
import type {
  makeCancelRsvp,
  makeCreateEvent,
  makeLoadCommunityEvents,
  makeLoadEvent,
  makeLoadNearbyEvents,
  makeRsvpToEvent,
} from './events'
import type { makeCreatePost, makeListJoinedCommunities } from './compose'
import type { makeLoadFeed } from './feed'
import type { makeCellPlaceName, makeResolveLocation } from './resolve-location'
import type { makeReadPostalCode, makeResolvePostalCode } from './resolve-postal-code'
import type { makeSubscribeToPosts } from './subscribe-to-posts'
import type { makeLoadReplies, makeLoadThread, makeReply } from './thread'
import type { makeToggleReaction } from './react'
import type { makeLogin } from './login'
import type { makeRegister } from './register'
import type { makeLogout } from './logout'
import type { makeRestoreSession } from './restore-session'
import type { makeGetProfile } from './get-profile'
import type { makeUpdateProfile } from './update-profile'
import type { makeSwitchNode } from './switch-node'
import type { makeReadServerUrl } from './read-server-url'
import type { makeTestNode } from './test-node'

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
  makeLoadCommunityEvents,
  makeLoadEvent,
  makeLoadNearbyEvents,
  makeRsvpToEvent,
  type DetailedEvent,
} from './events'
export { makeLoadFeed } from './feed'
export { makeCellPlaceName, makeResolveLocation, type LocationError, type ResolvedLocation } from './resolve-location'
export { makeReadPostalCode, makeResolvePostalCode } from './resolve-postal-code'
export { makeSubscribeToPosts } from './subscribe-to-posts'
export { makeLoadReplies, makeLoadThread, makeReply, type ReplyInput } from './thread'
export { makeToggleReaction } from './react'
export { makeLogin, type LoginInput } from './login'
export { makeLogout } from './logout'
export { makeRegister, type RegisterInput } from './register'
export { makeRefreshSession } from './refresh-session'
export { makeRestoreSession } from './restore-session'
export { makeGetProfile } from './get-profile'
export { makeUpdateProfile } from './update-profile'
export { makeSwitchNode } from './switch-node'
export { makeReadServerUrl } from './read-server-url'
export { makeTestNode } from './test-node'

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
  /** The post a thread screen opens on. */
  readonly loadThread: ReturnType<typeof makeLoadThread>
  /** One level of replies under a post, for "show replies". */
  readonly loadReplies: ReturnType<typeof makeLoadReplies>
  readonly reply: ReturnType<typeof makeReply>
  /** Leaves an emoji on a post or takes it back, and says what that emoji now counts. */
  readonly toggleReaction: ReturnType<typeof makeToggleReaction>
  readonly listJoinedCommunities: ReturnType<typeof makeListJoinedCommunities>
  readonly loadNearbyCommunities: ReturnType<typeof makeLoadNearbyCommunities>
  readonly loadCommunity: ReturnType<typeof makeLoadCommunity>
  readonly loadCommunityFeed: ReturnType<typeof makeLoadCommunityFeed>
  readonly joinCommunity: ReturnType<typeof makeJoinCommunity>
  readonly createCommunity: ReturnType<typeof makeCreateCommunity>
  readonly loadNearbyEvents: ReturnType<typeof makeLoadNearbyEvents>
  /** What one community has on, paged the same way. */
  readonly loadCommunityEvents: ReturnType<typeof makeLoadCommunityEvents>
  readonly loadEvent: ReturnType<typeof makeLoadEvent>
  readonly rsvpToEvent: ReturnType<typeof makeRsvpToEvent>
  readonly cancelRsvp: ReturnType<typeof makeCancelRsvp>
  readonly createEvent: ReturnType<typeof makeCreateEvent>
  /** Whose account this is, on the node it lives on. */
  readonly getProfile: ReturnType<typeof makeGetProfile>
  readonly updateProfile: ReturnType<typeof makeUpdateProfile>
  /** One health call to a node, before anything is written. */
  readonly testNode: ReturnType<typeof makeTestNode>
  readonly switchNode: ReturnType<typeof makeSwitchNode>
  /** The node this app points at; the built-in one until someone moves it. */
  readonly readServerUrl: ReturnType<typeof makeReadServerUrl>
  readonly sessionEvents: SessionEvents
}
