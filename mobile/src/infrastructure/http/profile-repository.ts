import { AxiosError, type AxiosInstance } from 'axios'

import { err, ok, type AuthError, type Profile, type ProfileRepository } from '../../domain'
import { PROFILE_PATH } from './endpoints'

/** What the node keeps about your own account. The handle never changes; the name is yours. */
type ProfileDto = { id: number; username: string; display_name: string }

const toProfile = ({ username, display_name: displayName }: ProfileDto): Profile => ({ handle: username, displayName })

/** A refused name is a different sentence from a refused password, so it is a different error. */
const toProfileError = (error: unknown): AuthError => {
  if (error instanceof AxiosError && error.response) {
    if (error.response.status === 400) return 'invalid-name'
    if (error.response.status === 401) return 'no-session'
    if (error.response.status === 404) return 'gone'
  }
  return error instanceof AxiosError && !error.response ? 'network' : 'unexpected'
}

/** Both calls are about one account: the one the bearer token belongs to. */
export const makeHttpProfileRepository = ({ http }: { http: Pick<AxiosInstance, 'get' | 'patch'> }): ProfileRepository => ({
  async read() {
    try {
      const { data } = await http.get<ProfileDto>(PROFILE_PATH)
      return ok(toProfile(data))
    } catch (error) {
      return err(toProfileError(error))
    }
  },

  async update(displayName) {
    try {
      const { data } = await http.patch<ProfileDto>(PROFILE_PATH, { display_name: displayName })
      return ok(toProfile(data))
    } catch (error) {
      return err(toProfileError(error))
    }
  },
})
