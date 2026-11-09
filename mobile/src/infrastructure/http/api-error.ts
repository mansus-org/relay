import { AxiosError } from 'axios'

import type { AdminError, ApiError } from '../../domain'

export const toApiError = (error: unknown): ApiError =>
  error instanceof AxiosError && !error.response ? 'network' : 'unexpected'

export const statusOf = (error: unknown): number | undefined => (error instanceof AxiosError ? error.response?.status : undefined)

/**
 * The refusals every `/admin` route shares.
 *
 * A 403 is its own answer here rather than a shrug: these screens are only reachable by being an
 * admin, so an account that stopped being one should be told that instead of a general failure.
 * A 401 is left alone - the client has already tried to refresh it by the time one gets here.
 */
export const toAdminError = (error: unknown): AdminError => {
  const status = statusOf(error)
  if (status === 403) return 'not-an-admin'
  if (status === 404) return 'not-found'
  if (status === 409) return 'already-decided'
  return toApiError(error)
}
