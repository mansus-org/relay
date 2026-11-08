import type { AxiosAdapter } from 'axios'

import {
  makeCellPlaceName,
  makeCreatePost,
  makeListJoinedCommunities,
  makeLoadFeed,
  makeLogin,
  makeLogout,
  makeRefreshSession,
  makeRegister,
  makeResolveLocation,
  makeRestoreSession,
  makeSubscribeToPosts,
  type UseCases,
} from '../application'
import type { LocationProvider, PlaceNamer } from '../domain'
import { makeHttpAuthRepository } from '../infrastructure/http/auth-repository'
import { makeHttpClient } from '../infrastructure/http/client'
import { makeHttpCommunityRepository, makeHttpFeedRepository, makeHttpPostRepository } from '../infrastructure/http/feed-repository'
import { makeExpoLocationProvider, makeExpoPlaceNamer } from '../infrastructure/location/expo-location'
import { makeH3CellEncoder } from '../infrastructure/location/h3-cell-encoder'
import { makeFetchPostStream, type StreamFetch } from '../infrastructure/stream/fetch-post-stream'
import { makeSessionEvents } from '../infrastructure/session-events'
import type { KeyValueStorage } from '../infrastructure/storage/key-value'
import { makeServerUrlStore } from '../infrastructure/storage/server-url-store'
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

/** The one place that knows which adapters implement which ports. */
export function wireUseCases({
  secureStorage,
  preferenceStorage,
  httpAdapter,
  fixedApiBaseUrl,
  streamFetch,
  locationProvider = makeExpoLocationProvider(),
  placeNamer = makeExpoPlaceNamer(),
}: WireDeps): UseCases {
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
  const postStream = makeFetchPostStream({ fetch: streamFetch ?? (globalThis.fetch as unknown as StreamFetch), getBaseUrl, getAccessToken })

  return {
    login: makeLogin({ authRepository, tokenWriter: tokenStore, serverUrlWriter: serverUrlStore }),
    register: makeRegister({ authRepository, tokenWriter: tokenStore }),
    logout,
    restoreSession: makeRestoreSession({ tokenReader: tokenStore, tokenWriter: tokenStore, refreshSession }),
    loadFeed: makeLoadFeed({ feedRepository: makeHttpFeedRepository({ http }) }),
    resolveLocation: makeResolveLocation({ locationProvider, cellEncoder, placeNamer }),
    placeNameOf: makeCellPlaceName({ cellEncoder, placeNamer }),
    subscribeToPosts: makeSubscribeToPosts({ postStream }),
    createPost: makeCreatePost({ postRepository: makeHttpPostRepository({ http }) }),
    listJoinedCommunities: makeListJoinedCommunities({ communityRepository: makeHttpCommunityRepository({ http }) }),
    sessionEvents,
  }
}
