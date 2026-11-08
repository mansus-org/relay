import type { AuthError } from './auth-error'
import type { AuthTokens, Credentials, RefreshedSession, Registration, Session } from './session'
import type { ApiError, Community, FeedPage, FeedQuery, LatLng, LocationStatus, NewPost, Post } from './post'
import type { Result } from './result'

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

export type PlaceNamer = {
  /** A human place name for a coordinate, or null when none can be resolved. */
  readonly nameOf: (position: LatLng) => Promise<string | null>
}
