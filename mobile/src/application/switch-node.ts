import {
  err,
  normalizeServerUrl,
  ok,
  serverUrlError,
  type NodeError,
  type NodeProbe,
  type Result,
  type ServerUrlWriter,
  type TokenWriter,
} from '../domain'

type Deps = {
  readonly nodeProbe: NodeProbe
  readonly serverUrlWriter: ServerUrlWriter
  readonly tokenWriter: Pick<TokenWriter, 'clear'>
}

/**
 * Move to another node. Nothing is written until the place has answered, and the first thing to
 * go is the session: a token one node minted means nothing at another, and keeping it would have
 * the app knock on a new door with an old key.
 *
 * Answers with the URL as it was stored. There is no auto-login on the other side, because each
 * node keeps its own accounts; the caller takes the person to the sign-in screen.
 */
export const makeSwitchNode =
  ({ nodeProbe, serverUrlWriter, tokenWriter }: Deps) =>
  async (url: string): Promise<Result<string, NodeError>> => {
    if (serverUrlError(url)) return err('bad-url')
    if (!(await nodeProbe.check(url)).reachable) return err('unreachable')
    await tokenWriter.clear()
    const saved = normalizeServerUrl(url)
    await serverUrlWriter.set(saved)
    return ok(saved)
  }
