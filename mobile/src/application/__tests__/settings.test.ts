import { DEFAULT_SERVER_URL, displayNameError, err, ok, type Profile } from '../../domain'
import { makeFakeNodeProbe, makeFakeProfileRepository, makeMemoryServerUrlStore, makeMemoryTokenStore, makeNodeTest } from '../../testing/fakes'
import { makeGetProfile, makeReadServerUrl, makeSwitchNode, makeTestNode, makeUpdateProfile } from '..'

const profile: Profile = { handle: 'ada', displayName: 'Ada L', isAdmin: false }

describe('readServerUrl', () => {
  it('answers with the node stored, which is the built-in one until someone moves', async () => {
    expect(await makeReadServerUrl({ serverUrlReader: makeMemoryServerUrlStore() })()).toBe(DEFAULT_SERVER_URL)
  })

  it('answers with wherever the person moved to', async () => {
    const store = makeMemoryServerUrlStore()
    await store.set('https://relay.example.org')
    expect(await makeReadServerUrl({ serverUrlReader: store })()).toBe('https://relay.example.org')
  })
})

describe('getProfile', () => {
  it('reads the account of whoever is signed in', async () => {
    const { repository, calls } = makeFakeProfileRepository({ read: ok(profile) })
    const getProfile = makeGetProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore({ accessToken: 'a1', refreshToken: 'r1' }) })

    expect(await getProfile()).toEqual(ok(profile))
    expect(calls.read).toBe(1)
  })

  it('says there is no session before it asks the node', async () => {
    const { repository, calls } = makeFakeProfileRepository({ read: ok(profile) })
    const getProfile = makeGetProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore() })

    expect(await getProfile()).toEqual(err('no-session'))
    expect(calls.read).toBe(0)
  })

  it('passes the node error straight through', async () => {
    const { repository } = makeFakeProfileRepository({ read: err('network') })
    const getProfile = makeGetProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore({ accessToken: 'a1' }) })
    expect(await getProfile()).toEqual(err('network'))
  })
})

describe('updateProfile', () => {
  it('sends the trimmed name and returns the profile as the node now keeps it', async () => {
    const { repository, calls } = makeFakeProfileRepository({ update: ok({ ...profile, displayName: 'Ada Lovelace' }) })
    const updateProfile = makeUpdateProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore({ accessToken: 'a1' }) })

    expect(await updateProfile('  Ada Lovelace ')).toEqual(ok({ ...profile, displayName: 'Ada Lovelace' }))
    expect(calls.update).toEqual(['Ada Lovelace'])
  })

  it.each(['', '   ', 'x'.repeat(61)])('refuses %s without asking the node', async (name) => {
    const { repository, calls } = makeFakeProfileRepository({ update: ok(profile) })
    const updateProfile = makeUpdateProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore({ accessToken: 'a1' }) })

    expect(await updateProfile(name)).toEqual(err('invalid-name'))
    expect(calls.update).toEqual([])
  })

  it('refuses when nobody is signed in', async () => {
    const { repository, calls } = makeFakeProfileRepository({ update: ok(profile) })
    const updateProfile = makeUpdateProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore() })

    expect(await updateProfile('Ada')).toEqual(err('no-session'))
    expect(calls.update).toEqual([])
  })

  it('passes the node error straight through', async () => {
    const { repository } = makeFakeProfileRepository({ update: err('invalid-credentials') })
    const updateProfile = makeUpdateProfile({ profileRepository: repository, tokenReader: makeMemoryTokenStore({ accessToken: 'a1' }) })
    expect(await updateProfile('Ada')).toEqual(err('invalid-credentials'))
  })
})

describe('displayNameError', () => {
  it.each(['', '   ', 'x'.repeat(61)])('rejects %s', (name) => {
    expect(displayNameError(name)).not.toBeNull()
  })

  it.each(['Ada', 'Ada Lovelace', 'x'.repeat(60)])('accepts %s', (name) => {
    expect(displayNameError(name)).toBeNull()
  })
})

describe('testNode', () => {
  it('probes the address and hands back what it found', async () => {
    const { probe, calls } = makeFakeNodeProbe({ 'https://friends.example': makeNodeTest('friends.example', { version: '0.4.1' }) })

    const result = await makeTestNode({ nodeProbe: probe })('https://friends.example')

    expect(result).toEqual(ok(makeNodeTest('friends.example', { version: '0.4.1' })))
    expect(calls).toEqual(['https://friends.example'])
  })

  it('reports a node that did not answer without calling it an error', async () => {
    const { probe } = makeFakeNodeProbe()
    const result = await makeTestNode({ nodeProbe: probe })('https://quiet.example')

    expect(result.ok).toBe(true)
    expect(result.ok && result.value.reachable).toBe(false)
  })

  it('refuses an address that cannot be a node, without going to the network', async () => {
    const { probe, calls } = makeFakeNodeProbe()
    expect(await makeTestNode({ nodeProbe: probe })('friends.example')).toEqual(err('bad-url'))
    expect(calls).toEqual([])
  })
})

describe('switchNode', () => {
  const url = 'https://friends.example'

  it('writes the new node and drops the session, because the old token means nothing there', async () => {
    const { probe } = makeFakeNodeProbe({ [url]: makeNodeTest('friends.example') })
    const tokens = makeMemoryTokenStore({ accessToken: 'a1', refreshToken: 'r1' })
    const serverUrl = makeMemoryServerUrlStore('https://relay.mansus.org')

    const result = await makeSwitchNode({ nodeProbe: probe, serverUrlWriter: serverUrl, tokenWriter: tokens })(url)

    expect(result).toEqual(ok(url))
    expect(await serverUrl.get()).toBe(url)
    expect(tokens.current()).toBeNull()
  })

  it('writes nothing when the node does not answer, so you keep the one you have', async () => {
    const { probe } = makeFakeNodeProbe()
    const tokens = makeMemoryTokenStore({ accessToken: 'a1' })
    const serverUrl = makeMemoryServerUrlStore('https://relay.mansus.org')

    expect(await makeSwitchNode({ nodeProbe: probe, serverUrlWriter: serverUrl, tokenWriter: tokens })('https://quiet.example')).toEqual(err('unreachable'))
    expect(await serverUrl.get()).toBe('https://relay.mansus.org')
    expect(tokens.current()).toEqual({ accessToken: 'a1' })
  })

  it('refuses an address that cannot be a node, without going to the network', async () => {
    const { probe, calls } = makeFakeNodeProbe()
    const tokens = makeMemoryTokenStore({ accessToken: 'a1' })
    expect(await makeSwitchNode({ nodeProbe: probe, serverUrlWriter: makeMemoryServerUrlStore(), tokenWriter: tokens })('not a url')).toEqual(err('bad-url'))
    expect(calls).toEqual([])
    expect(tokens.current()).not.toBeNull()
  })

  it('stores the address the way the app stores every address', async () => {
    const messy = ' https://friends.example/// '
    const { probe } = makeFakeNodeProbe({ [messy]: makeNodeTest('friends.example') })
    const serverUrl = makeMemoryServerUrlStore()
    await makeSwitchNode({ nodeProbe: probe, serverUrlWriter: serverUrl, tokenWriter: makeMemoryTokenStore() })(messy)
    expect(await serverUrl.get()).toBe(url)
  })
})
