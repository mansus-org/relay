// Relative to the API base URL (<server>/api).
export const LOGIN_PATH = '/auth/login'
export const REGISTER_PATH = '/auth/register'
export const REFRESH_PATH = '/auth/refresh'
/** PATCH with the bearer token: the account that token belongs to. */
export const PROFILE_PATH = '/auth/me'

// Feed and posts. Served by the backend (RELY-90).
export const FEED_PATH = '/feed'
export const POSTS_PATH = '/posts'
export const postPath = (id: string) => `${POSTS_PATH}/${encodeURIComponent(id)}`
export const postRepliesPath = (id: string) => `${postPath(id)}/replies`
export const postReactionsPath = (id: string) => `${postPath(id)}/reactions`
/** The emoji goes in the path, so it is encoded like any other path segment. */
export const reactionPath = (id: string, emoji: string) => `${postReactionsPath(id)}/${encodeURIComponent(emoji)}`

// Live stream. Served by the backend (RELY-91): one `post` event per post said near the cell.
export const STREAM_PATH = '/stream'
export const JOINED_COMMUNITIES_PATH = '/communities/joined'

// Communities. Assumed contract (RELY-89); the backend endpoints do not exist yet.
export const COMMUNITIES_PATH = '/communities'
export const communityPath = (id: string) => `/communities/${encodeURIComponent(id)}`
export const communityFeedPath = (id: string) => `${communityPath(id)}/feed`
export const communityJoinPath = (id: string) => `${communityPath(id)}/join`
/** What a community has on. Served by the backend (RELY-85); public, unlike the feed. */
export const communityEventsPath = (id: string) => `${communityPath(id)}/events`

// Location. Served by the backend (RELY-109).
export const postalCodePath = (code: string) => `/location/postal-code/${encodeURIComponent(code)}`

// Events. Served by the backend (RELY-92): reads are public, the three writes need a bearer token.
export const EVENTS_PATH = '/events'
export const eventPath = (id: string) => `${EVENTS_PATH}/${encodeURIComponent(id)}`
export const eventRsvpPath = (id: string) => `${eventPath(id)}/rsvp`
