import { err, ok, serverUrlError, type NodeError, type NodeProbe, type NodeTest, type Result } from '../domain'

/**
 * One call to the health endpoint of a node, for the screen to answer with before it offers
 * to move there. A URL that cannot be a node never reaches the network.
 */
export const makeTestNode =
  ({ nodeProbe }: { nodeProbe: NodeProbe }) =>
  async (url: string): Promise<Result<NodeTest, NodeError>> => {
    if (serverUrlError(url)) return err('bad-url')
    return ok(await nodeProbe.check(url))
  }
