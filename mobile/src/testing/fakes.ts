import {
  DEFAULT_SERVER_URL,
  type CellEncoder,
  type CommunityDetails,
  type LatLng,
  type LocationProvider,
  type PlaceNamer,
  type PostalArea,
  type PostalCodeError,
  type PostalCodeResolver,
  type ApiError,
  type NewPost,
  type PostRepository,
  type Reaction,
  err,
  ok,
  type AuthError,
  type AuthRepository,
  type AuthTokens,
  type Post,
  type RefreshedSession,
  type Result,
  type ServerUrlReader,
  type ServerUrlWriter,
  type Session,
  type TokenReader,
  type TokenWriter,
} from '../domain'
import type { KeyValueStorage } from '../infrastructure/storage/key-value'

export const makeMemoryStorage = (initial: Record<string, string> = {}): KeyValueStorage & { data: Map<string, string> } => {
  const data = new Map(Object.entries(initial))
  return {
    data,
    get: async (key) => data.get(key) ?? null,
    set: async (key, value) => void data.set(key, value),
    remove: async (key) => void data.delete(key),
  }
}

export const makeMemoryTokenStore = (
  initial: AuthTokens | null = null,
): TokenReader & TokenWriter & { current: () => AuthTokens | null } => {
  let tokens = initial
  return {
    current: () => tokens,
    load: async () => tokens,
    save: async ({ accessToken, refreshToken }) => {
      tokens = { accessToken, refreshToken: refreshToken ?? tokens?.refreshToken }
    },
    clear: async () => {
      tokens = null
    },
  }
}

export const makeMemoryServerUrlStore = (initial = DEFAULT_SERVER_URL): ServerUrlReader & ServerUrlWriter => {
  let url = initial
  return { get: async () => url, set: async (next) => void (url = next) }
}

type Scripted<T> = Result<T, AuthError> | (() => Promise<Result<T, AuthError>>)

/** An AuthRepository answering from scripted results; records the calls it receives. */
export const makeFakeAuthRepository = (script: { login?: Scripted<Session>; register?: Scripted<Session>; refresh?: Scripted<RefreshedSession> }) => {
  const calls = { login: [] as unknown[], register: [] as unknown[], refresh: [] as string[] }
  const answer = <T>(scripted: Scripted<T> | undefined) =>
    typeof scripted === 'function' ? scripted() : Promise.resolve(scripted ?? err<AuthError>('unexpected'))
  const repository: AuthRepository = {
    login: (credentials) => (calls.login.push(credentials), answer(script.login)),
    register: (registration) => (calls.register.push(registration), answer(script.register)),
    refresh: (refreshToken) => (calls.refresh.push(refreshToken), answer(script.refresh)),
  }
  return { repository, calls }
}

export const makePost = (id: string, overrides: Partial<Post> = {}): Post => ({
  id,
  author: { id: 'u1', name: 'bruno' },
  body: `post ${id}`,
  createdAt: '2026-10-29T12:00:00Z',
  locationCell: null,
  parentId: null,
  reactions: [],
  replyCount: 0,
  ...overrides,
})

type ScriptedPost<T> = Result<T, ApiError> | (() => Promise<Result<T, ApiError>>)

/** A PostRepository answering from scripted results; records the calls it receives. */
export const makeFakePostRepository = (
  script: {
    get?: ScriptedPost<Post>
    replies?: ScriptedPost<readonly Post[]>
    create?: ScriptedPost<Post>
    react?: ScriptedPost<Reaction>
    unreact?: ScriptedPost<void>
  } = {},
) => {
  const calls = {
    get: [] as string[],
    replies: [] as string[],
    create: [] as NewPost[],
    react: [] as { postId: string; emoji: string }[],
    unreact: [] as { postId: string; emoji: string }[],
  }
  const answer = <T>(scripted: ScriptedPost<T> | undefined): Promise<Result<T, ApiError>> =>
    typeof scripted === 'function' ? scripted() : Promise.resolve(scripted ?? err<ApiError>('unexpected'))
  const repository: PostRepository = {
    get: (id) => (calls.get.push(id), answer(script.get)),
    listReplies: (postId) => (calls.replies.push(postId), answer(script.replies)),
    create: (post) => (calls.create.push(post), answer(script.create)),
    react: (postId, emoji) => (calls.react.push({ postId, emoji }), answer(script.react)),
    unreact: (postId, emoji) => (calls.unreact.push({ postId, emoji }), answer(script.unreact)),
  }
  return { repository, calls }
}

export const makePostDto = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  author: { id: 'u1', name: 'bruno' },
  body: `post ${id}`,
  created_at: '2026-10-29T12:00:00Z',
  location_cell: '88a8100d6dfffff',
  reactions: [{ emoji: '🔥', count: 4, mine: true }],
  reply_count: 3,
  ...extra,
})

/** A LocationProvider with a settable permission and position; counts permission prompts. */
export const makeFakeLocationProvider = (initial: { granted: boolean; canAskAgain?: boolean; grantOnRequest?: boolean; position?: LatLng | null }) => {
  let status = { granted: initial.granted, canAskAgain: initial.canAskAgain ?? true }
  const calls = { request: 0 }
  const provider: LocationProvider = {
    status: async () => status,
    request: async () => {
      calls.request += 1
      status = { granted: initial.grantOnRequest ?? false, canAskAgain: false }
      return status
    },
    currentPosition: async () => (initial.position === undefined ? { lat: -23.5614, lng: -46.6919 } : initial.position),
  }
  return { provider, calls }
}

export const makeFakeCellEncoder = (): CellEncoder => ({
  cellOf: ({ lat, lng }) => `cell:${lat.toFixed(2)},${lng.toFixed(2)}`,
  centerOf: (cell) => {
    const [lat, lng] = cell.replace('cell:', '').split(',').map(Number)
    return { lat: lat!, lng: lng! }
  },
})

export const makeFakePlaceNamer = (name: string | null = 'Pinheiros, São Paulo') => {
  const calls: LatLng[] = []
  const namer: PlaceNamer = { nameOf: async (position) => (calls.push(position), name) }
  return { namer, calls }
}

export const makePostalArea = (postalCode: string, placeName: string, cell: string): PostalArea => ({ postalCode, placeName, cell })

/** A PostalCodeResolver answering from a map; anything it was not told about is not found. */
export const makeFakePostalCodeResolver = (
  areas: Record<string, PostalArea> = {},
  failure: PostalCodeError = { reason: 'not-found', message: '' },
): PostalCodeResolver & { calls: string[] } => {
  const calls: string[] = []
  return {
    calls,
    resolve: (code) => {
      calls.push(code)
      const area = areas[code]
      return Promise.resolve(area ? ok(area) : err(failure))
    },
  }
}

export const makeCommunity = (id: string, overrides: Partial<CommunityDetails> = {}): CommunityDetails => ({
  id,
  name: `Community ${id}`,
  description: `About ${id}`,
  memberCount: 10,
  locationCell: null,
  radiusKm: null,
  allowPseudonyms: false,
  isMember: false,
  createdBy: null,
  createdAt: null,
  ...overrides,
})

export const makeCommunityDto = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  name: `Community ${id}`,
  description: `About ${id}`,
  member_count: 84,
  location_cell: 'cell:-23.56,-46.69',
  radius_km: 5,
  allow_pseudonyms: true,
  is_member: false,
  created_by: { id: 'u9', name: 'alice' },
  created_at: '2026-07-29T12:00:00Z',
  ...extra,
})
