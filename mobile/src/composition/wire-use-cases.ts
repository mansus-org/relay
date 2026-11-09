import type { AxiosAdapter } from 'axios'
import { Platform } from 'react-native'

import {
  makeCellPlaceName,
  makeCreateCommunity,
  makeCreatePost,
  makeJoinCommunity,
  makeListJoinedCommunities,
  makeLoadCommunity,
  makeLoadCommunityFeed,
  makeLoadFeed,
  makeLoadNearbyCommunities,
  makeCancelRsvp,
  makeCreateEvent,
  makeLoadEvent,
  makeLoadNearbyEvents,
  makeLoadReplies,
  makeLoadThread,
  makeRsvpToEvent,
  makeReply,
  makeToggleReaction,
  makeLogin,
  makeLogout,
  makeReadPostalCode,
  makeRefreshSession,
  makeRegister,
  makeResolveLocation,
  makeResolvePostalCode,
  makeRestoreSession,
  makeSubscribeToPosts,
  type UseCases,
} from '../application'
import type { LocationProvider, PlaceNamer } from '../domain'
import { makeHttpAuthRepository } from '../infrastructure/http/auth-repository'
import { makeHttpClient } from '../infrastructure/http/client'
import { makeHttpCommunityRepository } from '../infrastructure/http/community-repository'
import { makeHttpEventRepository } from '../infrastructure/http/event-repository'
import { makeHttpFeedRepository, makeHttpPostRepository } from '../infrastructure/http/feed-repository'
import { makeHttpPostalCodeResolver } from '../infrastructure/http/postal-code-repository'
import { makeBrowserLocationProvider } from '../infrastructure/location/browser-geolocation'
import { makeExpoLocationProvider, makeExpoPlaceNamer } from '../infrastructure/location/expo-location'
import { makeH3CellEncoder } from '../infrastructure/location/h3-cell-encoder'
import { makeFetchPostStream, type StreamFetch } from '../infrastructure/stream/fetch-post-stream'
import { makeSessionEvents } from '../infrastructure/session-events'
import type { KeyValueStorage } from '../infrastructure/storage/key-value'
import { makeServerUrlStore } from '../infrastructure/storage/server-url-store'
import { makePostalCodeStore } from '../infrastructure/storage/postal-code-store'
import { makeTokenStore } from '../infrastructure/storage/token-store'

const API_PREFIX = '/api'

export type WireDeps = {
  readonly secureStorage: KeyValueStorage
  readonly preferenceStorage: KeyValueStorage
  /** Replaces axios' network adapter; tests use it to fake the server. */
  readonly httpAdapter?: AxiosAdapter
  /** API base URL that ignores the stored server URL; the web build is served by its own backend. */
  readonly fixedApiBaseUrl?: string
  /** Streaming fetch for the live feed (`expo/fetch`); tests fake it. */
  readonly streamFetch?: StreamFetch
  /** Replace the device location services; tests fake them. */
  readonly locationProvider?: LocationProvider
  readonly placeNamer?: PlaceNamer
}

/** The device geocoder that names a place does not exist on the web, so there is nothing to name it with. */
const noPlaceName: PlaceNamer = { nameOf: async () => null }

/** The one place that knows which adapters implement which ports. */
export function wireUseCases({
  secureStorage,
  preferenceStorage,
  httpAdapter,
  fixedApiBaseUrl,
  streamFetch,
  locationProvider,
  placeNamer,
}: WireDeps): UseCases {
  // A phone has a GPS chip and a geocoder; the web has the browser's own guess at where it is, and nothing to name it with.
  const web = Platform.OS === 'web'
  const location = locationProvider ?? (web ? makeBrowserLocationProvider() : makeExpoLocationProvider())
  const namer = placeNamer ?? (web ? noPlaceName : makeExpoPlaceNamer())
  const tokenStore = makeTokenStore({ storage: secureStorage })
  const serverUrlStore = makeServerUrlStore({ storage: preferenceStorage })
  const sessionEvents = makeSessionEvents()

  // The client needs refreshSession and the repository (behind refreshSession) needs the client;
  // the closures below are only called once a request is made, after everything is wired.
  const getBaseUrl = async () => fixedApiBaseUrl ?? `${await serverUrlStore.get()}${API_PREFIX}`
  const getAccessToken = async () => (await tokenStore.load())?.accessToken ?? null
  const http = makeHttpClient({
    getBaseUrl,
    getAccessToken,
    refreshAccessToken: async () => {
      const result = await refreshSession()
      return result.ok ? result.value.tokens.accessToken : null
    },
    onUnauthorized: async () => {
      await logout()
      sessionEvents.notifyExpired()
    },
  })
  if (httpAdapter) http.defaults.adapter = httpAdapter

  const authRepository = makeHttpAuthRepository({ http })
  const refreshSession = makeRefreshSession({ authRepository, tokenReader: tokenStore, tokenWriter: tokenStore })
  const logout = makeLogout({ tokenWriter: tokenStore })
  const cellEncoder = makeH3CellEncoder()
  const postalCodeStore = makePostalCodeStore({ storage: preferenceStorage })
  const communityRepository = makeHttpCommunityRepository({ http })
  const eventRepository = makeHttpEventRepository({ http })
  const postStream = makeFetchPostStream({ fetch: streamFetch ?? (globalThis.fetch as unknown as StreamFetch), getBaseUrl, getAccessToken })
  const postRepository = makeHttpPostRepository({ http })

  return {
    login: makeLogin({ authRepository, tokenWriter: tokenStore, serverUrlWriter: serverUrlStore }),
    register: makeRegister({ authRepository, tokenWriter: tokenStore }),
    logout,
    restoreSession: makeRestoreSession({ tokenReader: tokenStore, tokenWriter: tokenStore, refreshSession }),
    loadFeed: makeLoadFeed({ feedRepository: makeHttpFeedRepository({ http }) }),
    resolveLocation: makeResolveLocation({ locationProvider: location, cellEncoder, placeNamer: namer }),
    resolvePostalCode: makeResolvePostalCode({ resolver: makeHttpPostalCodeResolver({ http }), store: postalCodeStore }),
    readPostalCode: makeReadPostalCode({ store: postalCodeStore }),
    placeNameOf: makeCellPlaceName({ cellEncoder, placeNamer: namer }),
    subscribeToPosts: makeSubscribeToPosts({ postStream }),
    createPost: makeCreatePost({ postRepository }),
    loadThread: makeLoadThread({ postRepository }),
    loadReplies: makeLoadReplies({ postRepository }),
    reply: makeReply({ postRepository }),
    toggleReaction: makeToggleReaction({ postRepository }),
    listJoinedCommunities: makeListJoinedCommunities({ communityRepository }),
    loadNearbyCommunities: makeLoadNearbyCommunities({ communityRepository, cellEncoder }),
    loadCommunity: makeLoadCommunity({ communityRepository, cellEncoder }),
    loadCommunityFeed: makeLoadCommunityFeed({ communityRepository }),
    joinCommunity: makeJoinCommunity({ communityRepository }),
    createCommunity: makeCreateCommunity({ communityRepository }),
    loadNearbyEvents: makeLoadNearbyEvents({ eventRepository, cellEncoder }),
    loadEvent: makeLoadEvent({ eventRepository, cellEncoder }),
    rsvpToEvent: makeRsvpToEvent({ eventRepository, cellEncoder }),
    cancelRsvp: makeCancelRsvp({ eventRepository, cellEncoder }),
    createEvent: makeCreateEvent({ eventRepository, cellEncoder }),
    sessionEvents,
  }
}
