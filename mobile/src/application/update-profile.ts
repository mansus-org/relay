import { displayNameError, err, type AuthError, type Profile, type ProfileRepository, type Result, type TokenReader } from '../domain'

type Deps = {
  readonly profileRepository: Pick<ProfileRepository, 'update'>
  /** The name belongs to a session; with no token stored there is nobody to rename. */
  readonly tokenReader: TokenReader
}

/**
 * Writes a new display name for whoever is signed in, and hands back the profile as the node
 * now keeps it. The handle is not part of this: it is what other people's posts lean on.
 */
export const makeUpdateProfile =
  ({ profileRepository, tokenReader }: Deps) =>
  async (displayName: string): Promise<Result<Profile, AuthError>> => {
    // The field says why in a sentence; this is the backstop for whoever calls without looking.
    if (displayNameError(displayName)) return err('invalid-name')
    if (!(await tokenReader.load())) return err('no-session')
    return profileRepository.update(displayName.trim())
  }
