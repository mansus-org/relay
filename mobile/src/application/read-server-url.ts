import type { ServerUrlReader } from '../domain'

type Deps = {
  readonly serverUrlReader: ServerUrlReader
}

/**
 * The node this app points at. Nobody having moved yet is not an empty answer: the address built
 * into the app is what is being pointed at, and the settings row shows it as such.
 */
export const makeReadServerUrl =
  ({ serverUrlReader }: Deps) =>
  async (): Promise<string> => serverUrlReader.get()
