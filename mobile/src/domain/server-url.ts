export const DEFAULT_SERVER_URL = 'https://relay.mansus.org'

/** The default as it is shown to a person: a host, not a URL with a scheme on the front. */
export const DEFAULT_SERVER_HOST = 'relay.mansus.org'

export const normalizeServerUrl = (url: string): string => url.trim().replace(/\/+$/, '')

/**
 * The host as it is shown in the interface: no scheme, no path, no trailing slash.
 * Whatever the person typed, this is what the row reads back to them.
 */
export const serverHost = (url: string): string =>
  normalizeServerUrl(url)
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, '')
    .replace(/^\/\//, '')
    .split('/')[0]!

/** Hosts a phone can reach without TLS: a loopback or a `.local` / LAN name typed on purpose. */
const isLocalHost = (host: string): boolean =>
  host === 'localhost' ||
  host === '127.0.0.1' ||
  host === '[::1]' ||
  host.endsWith('.local') ||
  /^\d{1,3}(\.\d{1,3}){3}$/.test(host)

/** A dotted name or a bracketed IPv6 address. Not a sentence, not a path, not a port on its own. */
const isHost = (host: string): boolean =>
  /^\[[0-9a-f:.]+\]$/i.test(host) ||
  /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/.test(host)

/**
 * Why this address cannot be a Relay node, in the words the field shows. Null when it can.
 *
 * The address is typed on a phone, so the checks are the ones a thumb actually trips over:
 * a forgotten scheme, a host with nothing after it, a whole sentence pasted from a browser.
 */
export const serverUrlError = (url: string): string | null => {
  const value = url.trim()
  if (!value) return 'A server address, or leave it as the default.'
  if (/\s/.test(value)) return 'One address, with no spaces in it.'
  const address = /^(https?):\/\/([^/]*)(?:\/.*)?$/i.exec(value)
  if (!address) return 'Start it with http:// or https://.'
  const [, scheme, authority = ''] = address
  // A user and password in the address is not a node, it is someone else's mistake.
  if (!authority || authority.includes('@')) return 'A server address, with a host in it.'
  const [host, port] = authority.split(':')
  if (!isHost(host ?? '')) return 'That is not a host Relay can read.'
  if (port !== undefined && !/^\d{1,5}$/.test(port)) return 'A port is numbers only.'
  // A plain http node is allowed on a LAN, which is the only place a phone meets one without
  // a certificate. Anywhere else, your token would be travelling in the clear.
  if (scheme!.toLowerCase() === 'http' && !isLocalHost(host!)) return 'Use https:// unless it is a local test server.'
  return null
}
