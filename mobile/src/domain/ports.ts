import type { AuthError } from './auth-error'
import type { NodeTest } from './node-test'
import type { AuthTokens, Credentials, RefreshedSession, Registration, Session } from './session'
import type { ApiError, Community, FeedPage, FeedQuery, LatLng, LocationStatus, NewPost, Post } from './post'
import type { Result } from './result'
import type { CommunityDetails, CommunityError, CommunityFeedQuery, JoinRequest, NewCommunity } from './community'
import type { Event, EventDetail, EventError, EventPage, NewEvent } from './event'
import type { PostalArea, PostalCodeError } from './postal-code'
import type { Profile } from './user'

export type AuthRepository = {
  readonly login: (credentials: Credentials) => Promise<Result<Session, AuthError>>
  readonly register: (registration: Registration) => Promise<Result<Session, AuthError>>
  readonly refresh: (refreshToken: string) => Promise<Result<RefreshedSession, AuthError>>
}

export type TokenReader = {
  /** Null when no access token is stored. */
  readonly load: () => Promise<AuthTokens | null>
}

export type TokenWriter = {
  /** An undefined refresh token leaves the stored one untouched. */
  readonly save: (tokens: AuthTokens) => Promise<void>
  readonly clear: () => Promise<void>
}

export type ServerUrlReader = {
  /** The stored server URL, or the default when none is stored. */
  readonly get: () => Promise<string>
}

export type ServerUrlWriter = {
  readonly set: (url: string) => Promise<void>
}

export type ProfileRepository = {
  /** Whose account the stored bearer token belongs to. */
  readonly read: () => Promise<Result<Profile, AuthError>>
  /** 'invalid-name' when the server refuses the name; 'gone' when the account is no longer there. */
  readonly update: (displayName: string) => Promise<Result<Profile, AuthError>>
}

export type NodeProbe = {
  /** One health call to one node. Never throws: what went wrong comes back in the answer. */
  readonly check: (url: string) => Promise<NodeTest>
}

export type SessionEvents = {
  /** Fires when the session can no longer be refreshed. Returns an unsubscribe function. */
  readonly onExpired: (handler: () => void) => () => void
}

export type FeedRepository = {
  readonly list: (query: FeedQuery) => Promise<Result<FeedPage, ApiError>>
}

export type PostRepository = {
  readonly create: (post: NewPost) => Promise<Result<Post, ApiError>>
}

export type CommunityRepository = {
  /** Communities the signed-in user has joined; empty when there are none. */
  readonly listJoined: () => Promise<Result<readonly Community[], ApiError>>
  /** Communities whose anchor is near the cell, in the server's order. */
  readonly listNearby: (cell: string) => Promise<Result<readonly CommunityDetails[], ApiError>>
  readonly get: (id: string) => Promise<Result<CommunityDetails, CommunityError>>
  /** 'out-of-range' when the server refuses the cell the user joins from. */
  readonly join: (request: JoinRequest) => Promise<Result<void, CommunityError>>
  readonly create: (community: NewCommunity) => Promise<Result<CommunityDetails, ApiError>>
  /** Posts of a community, newest first; 'forbidden' for non-members. */
  readonly feed: (query: CommunityFeedQuery) => Promise<Result<FeedPage, CommunityError>>
}

export type EventRepository = {
  /** Events whose cell is within the query's reach, soonest first; `from` is a date, an instant or 'past'. */
  readonly list: (query: { cell: string; radiusKm: number; from?: string }) => Promise<Result<EventPage<Event>, ApiError>>
  /** 'not-found' when there is no such event; `userRsvped` is only ever true behind a token. */
  readonly get: (id: string) => Promise<Result<EventDetail, EventError>>
  readonly create: (event: NewEvent) => Promise<Result<Event, EventError>>
  /** The new head count. 'already-going' when you were already on the list. */
  readonly rsvp: (id: string) => Promise<Result<number, EventError>>
  /** 'not-going' when there was no RSVP of yours to take back. */
  readonly cancelRsvp: (id: string) => Promise<Result<void, EventError>>
}

export type PostStream = {
  /** Calls onPost for each new post in the cell until the returned unsubscribe function is called. */
  readonly subscribe: (cell: string, onPost: (post: Post) => void) => () => void
}

export type LocationProvider = {
  /** Current permission, without prompting. */
  readonly status: () => Promise<LocationStatus>
  /** Prompts for permission when the OS still allows it. */
  readonly request: () => Promise<LocationStatus>
  /** Null when the position could not be read. */
  readonly currentPosition: () => Promise<LatLng | null>
}

export type CellEncoder = {
  readonly cellOf: (position: LatLng) => string
  readonly centerOf: (cell: string) => LatLng
}

export type PostalCodeResolver = {
  /** The place a postal code names, or why it has none. */
  readonly resolve: (code: string) => Promise<Result<PostalArea, PostalCodeError>>
}

export type PostalCodeReader = {
  /** The postal code the user last chose, or null when they never chose one. */
  readonly read: () => Promise<string | null>
}

export type PostalCodeWriter = {
  readonly save: (code: string) => Promise<void>
}

export type PlaceNamer = {
  /** A human place name for a coordinate, or null when none can be resolved. */
  readonly nameOf: (position: LatLng) => Promise<string | null>
}
