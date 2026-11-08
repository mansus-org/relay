import type { Href } from 'expo-router'

export type AuthGroup = 'auth' | 'app'

/**
 * Routes a stranger cannot open, because everything behind them writes: composing, and the
 * communities a member joins. Reading is public, so the feed is not in this list.
 */
export const MEMBER_ROUTES = ['/compose', '/communities'] as const

/** `/communities` and anything under it, but not a route that merely starts with the same word. */
export const isMemberRoute = (pathname: string | null): boolean =>
  MEMBER_ROUTES.some((route) => pathname === route || (pathname?.startsWith(`${route}/`) ?? false))

export type AuthRedirectInput = {
  group: AuthGroup
  /** The route being opened; only the (app) group needs it. */
  pathname?: string | null
  signedIn: boolean
  isLoading: boolean
  /** Where a stranger may read without an account: the web build, which anyone can open. */
  anonymousReading?: boolean
}

/**
 * Where a route group must send the visitor, or null to render it. The (auth) group is only for
 * signed-out visitors; a member is moved back to the feed. While the stored session is being
 * verified nothing redirects, so a valid session never flashes the login screen.
 *
 * On the web a stranger reads the feed: only the routes in MEMBER_ROUTES send them to /login.
 */
export function authRedirect({
  group,
  pathname,
  signedIn,
  isLoading,
  anonymousReading = false,
}: AuthRedirectInput): Href | null {
  if (isLoading) return null
  if (group === 'auth') return signedIn ? '/' : null
  if (signedIn) return null
  return anonymousReading && !isMemberRoute(pathname ?? null) ? null : '/login'
}
