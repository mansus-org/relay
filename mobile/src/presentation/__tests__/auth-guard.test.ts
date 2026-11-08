import { authRedirect, isMemberRoute } from '../auth-guard'

const app = (pathname: string, over: { signedIn?: boolean; anonymousReading?: boolean } = {}) =>
  authRedirect({ group: 'app', pathname, signedIn: false, isLoading: false, ...over })

describe('authRedirect', () => {
  it('sends a signed-out visitor from the app group to /login', () => {
    expect(authRedirect({ group: 'app', pathname: '/', signedIn: false, isLoading: false })).toBe('/login')
  })

  it('lets a signed-in user into the app group', () => {
    expect(authRedirect({ group: 'app', pathname: '/', signedIn: true, isLoading: false })).toBeNull()
  })

  it('lets a signed-out visitor see login and join', () => {
    expect(authRedirect({ group: 'auth', pathname: '/login', signedIn: false, isLoading: false })).toBeNull()
  })

  it('moves a signed-in user out of the auth group to the feed', () => {
    expect(authRedirect({ group: 'auth', pathname: '/login', signedIn: true, isLoading: false })).toBe('/')
  })

  it.each(['app', 'auth'] as const)('does not redirect %s while the session is being restored', (group) => {
    expect(authRedirect({ group, pathname: '/', signedIn: false, isLoading: true })).toBeNull()
  })

  describe('where a stranger may read (the web)', () => {
    it('leaves them on the feed', () => {
      expect(app('/', { anonymousReading: true })).toBeNull()
    })

    it.each(['/compose', '/communities', '/communities/12', '/communities/new'])(
      'sends them to /login from the members-only %s',
      (pathname) => {
        expect(app(pathname, { anonymousReading: true })).toBe('/login')
      },
    )

    it('never moves a signed-in reader', () => {
      expect(authRedirect({ group: 'app', pathname: '/compose', signedIn: true, isLoading: false, anonymousReading: true })).toBeNull()
    })
  })
})

describe('isMemberRoute', () => {
  it.each(['/compose', '/communities', '/communities/12'])('matches %s', (pathname) => {
    expect(isMemberRoute(pathname)).toBe(true)
  })

  it.each(['/', '/community-notes', null])('does not match %s', (pathname) => {
    expect(isMemberRoute(pathname)).toBe(false)
  })
})
