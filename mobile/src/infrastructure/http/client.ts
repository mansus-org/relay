import axios, { AxiosError, type AxiosInstance } from 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** Do not refresh tokens or trigger onUnauthorized when this request gets a 401. */
    skipAuthRefresh?: boolean
    /** Set by the response interceptor once the request has been retried. */
    authRetried?: boolean
  }
}

export type HttpClientDeps = {
  /** Read on every request, so a changed server URL applies immediately. */
  readonly getBaseUrl: () => Promise<string>
  readonly getAccessToken: () => Promise<string | null>
  /** Resolves to the new access token, or null when the session could not be refreshed. */
  readonly refreshAccessToken: () => Promise<string | null>
  /** Called after a failed refresh, once; the caller ends the session and redirects to login. */
  readonly onUnauthorized: () => Promise<void> | void
}

export function makeHttpClient({
  getBaseUrl,
  getAccessToken,
  refreshAccessToken,
  onUnauthorized,
}: HttpClientDeps): AxiosInstance {
  const http = axios.create() // eslint-disable-line import/no-named-as-default-member

  http.interceptors.request.use(async (config) => {
    config.baseURL = await getBaseUrl()
    const token = await getAccessToken()
    if (token) config.headers.set('Authorization', `Bearer ${token}`)
    return config
  })

  http.interceptors.response.use(undefined, async (error: unknown) => {
    if (!(error instanceof AxiosError) || error.response?.status !== 401 || !error.config) {
      throw error
    }
    const original = error.config
    if (original.authRetried || original.skipAuthRefresh) throw error
    // With no access token there is no session to refresh. A stranger's 401 is a refused read, and
    // ending a session they never had would throw them out of the feed and onto the login screen.
    if (!(await getAccessToken())) throw error
    original.authRetried = true
    const accessToken = await refreshAccessToken().catch(() => null)
    if (!accessToken) {
      await onUnauthorized()
      throw error
    }
    original.headers.set('Authorization', `Bearer ${accessToken}`)
    return http.request(original)
  })

  return http
}
