import { err, type AuthError, type Profile, type ProfileRepository, type Result, type TokenReader } from '../domain'

type Deps = {
  readonly profileRepository: Pick<ProfileRepository, 'read'>
  readonly tokenReader: TokenReader
}

/**
 * The account on the node you are standing on, for the settings screen to show. With no token
 * stored there is nobody to show, and the screen says so rather than guessing.
 */
export const makeGetProfile =
  ({ profileRepository, tokenReader }: Deps) =>
  async (): Promise<Result<Profile, AuthError>> => {
    if (!(await tokenReader.load())) return err('no-session')
    return profileRepository.read()
  }
