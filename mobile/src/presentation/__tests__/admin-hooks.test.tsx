import { act, create } from 'react-test-renderer'

import type { UseCases } from '../../application'
import { err, ok, type AdminError, type AdminMember, type Invite, type ModeratedPost } from '../../domain'
import { useAdminInvites } from '../use-admin-invites'
import { useAdminMembers } from '../use-admin-members'
import { useAdminPost } from '../use-admin-post'
import { markDecided, useAdminQueue } from '../use-admin-queue'
import { UseCasesProvider } from '../use-cases'

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const flush = () => act(async () => void (await new Promise((r) => setTimeout(r, 0))))

const failed = (error: AdminError) => err<AdminError>(error)

function mount<T>(hook: () => T, overrides: Partial<UseCases>) {
  const result = { current: undefined as unknown as T }
  function Probe() {
    result.current = hook()
    return null
  }
  let renderer: ReturnType<typeof create>
  act(() => {
    renderer = create(
      <UseCasesProvider useCases={overrides as UseCases}>
        <Probe />
      </UseCasesProvider>,
    )
  })
  return { result, unmount: () => act(() => renderer.unmount()) }
}

/** The screens ask for the list when they come into focus; a mounted hook has asked for nothing yet. */
const load = (refresh: () => Promise<void>) => act(async () => void (await refresh()))

const post = (id: string, overrides: Partial<ModeratedPost> = {}): ModeratedPost => ({
  id,
  body: `Body of ${id}`,
  createdAt: '2025-03-12T10:00:00',
  authorId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  status: 'pending',
  communityId: null,
  parentId: null,
  ai: null,
  ...overrides,
})

const member = (id: number, overrides: Partial<AdminMember> = {}): AdminMember => ({
  id,
  name: `Member ${id}`,
  handle: `member${id}`,
  joinedAt: '2025-03-12T10:00:00',
  isAdmin: false,
  deactivatedAt: null,
  ...overrides,
})

const invite = (id: number, overrides: Partial<Invite> = {}): Invite => ({
  id,
  token: `token-${id}`,
  url: null,
  note: null,
  state: 'open',
  createdAt: '2025-03-12T10:00:00',
  usedAt: null,
  usedById: null,
  revokedAt: null,
  ...overrides,
})

const asAdmin = { getProfile: jest.fn(async () => ok({ handle: 'ada', displayName: 'Ada', isAdmin: true })) }
const atNode = { readServerUrl: jest.fn(async () => 'https://relay.example/api') }

describe('useAdminQueue', () => {
  it('shows what the node says is waiting, and nothing before it answers', async () => {
    const loadQueue = jest.fn(async () => ok([post('p2'), post('p1')]))
    const t = mount(useAdminQueue, { loadQueue })
    expect(t.result.current.state.loaded).toBe(false)
    await load(t.result.current.refresh)
    expect(t.result.current.state.loaded).toBe(true)
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['p2', 'p1'])
    expect(t.result.current.state.problem).toBeNull()
  })

  it('keeps the queue that is on screen when a refresh will not come', async () => {
    const loadQueue = jest.fn().mockResolvedValueOnce(ok([post('p1')])).mockResolvedValueOnce(failed('network'))
    const t = mount(useAdminQueue, { loadQueue })
    await load(t.result.current.refresh)
    await load(t.result.current.refresh)
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['p1'])
    expect(t.result.current.state.problem).toBe('Could not reach Relay. Check your connection and try again.')
  })

  it('drops a post you settled on its own page, before the node has even answered', async () => {
    let answer!: (posts: ModeratedPost[]) => void
    const loadQueue = jest
      .fn()
      .mockResolvedValueOnce(ok([post('q1'), post('q2')]))
      .mockImplementation(() => new Promise((resolve) => (answer = (posts) => resolve(ok(posts)))))
    const t = mount(useAdminQueue, { loadQueue })
    await load(t.result.current.refresh)

    markDecided('q1')
    act(() => void t.result.current.refresh())
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['q2'])

    // What the node finally sends is the list, whatever was on screen while it was on its way.
    await act(async () => answer([post('q2')]))
    expect(t.result.current.state.posts.map((p) => p.id)).toEqual(['q2'])
    t.unmount()
  })
})

describe('useAdminPost', () => {
  it('reads the post again rather than trusting what the queue carried', async () => {
    const loadModeratedPost = jest.fn(async () => ok(post('p1', { status: 'approved' })))
    const t = mount(() => useAdminPost('p1'), { loadModeratedPost })
    await flush()
    expect(loadModeratedPost).toHaveBeenCalledWith({ id: 'p1' })
    expect(t.result.current.state.post?.status).toBe('approved')
  })

  it('says the post is gone when the node does not have it', async () => {
    const t = mount(() => useAdminPost('p1'), { loadModeratedPost: jest.fn(async () => failed('not-found')) })
    await flush()
    expect(t.result.current.state.post).toBeNull()
    expect(t.result.current.state.problem).toBe('That is not on this node any more.')
  })

  it('reports whether the node took the decision, and tells the screen when another admin got there first', async () => {
    const reviewPost = jest.fn(async () => failed('already-decided'))
    const t = mount(() => useAdminPost('p1'), { reviewPost, loadModeratedPost: jest.fn(async () => ok(post('p1'))) })
    await flush()
    let taken: boolean | undefined
    await act(async () => {
      taken = await t.result.current.decide('remove', 'contact details')
    })
    expect(taken).toBe(false)
    expect(reviewPost).toHaveBeenCalledWith({ id: 'p1', action: 'remove', reason: 'contact details' })
    expect(t.result.current.state.problem).toBe('Somebody got there first. Pull to see the queue again.')
    expect(t.result.current.state.busy).toBe(false)
  })
})

describe('useAdminMembers', () => {
  it('lists the accounts and learns your own handle so the sheet can keep its hands off it', async () => {
    const t = mount(useAdminMembers, { ...asAdmin, loadMembers: jest.fn(async () => ok([member(1), member(2)])) })
    await flush()
    await load(t.result.current.refresh)
    expect(t.result.current.state.members.map((m) => m.handle)).toEqual(['member1', 'member2'])
    expect(t.result.current.state.myHandle).toBe('ada')
  })

  it("reads a member's trail when the sheet opens, and not before", async () => {
    const loadMember = jest.fn(async () => ok({ member: member(3), history: [] }))
    const t = mount(useAdminMembers, { ...asAdmin, loadMembers: jest.fn(async () => ok([member(3)])) , loadMember })
    await flush()
    await load(t.result.current.refresh)
    expect(loadMember).not.toHaveBeenCalled()
    await act(async () => void (await t.result.current.openMember(3)))
    expect(loadMember).toHaveBeenCalledWith({ id: 3 })
    expect(t.result.current.state.open?.member.id).toBe(3)
    await act(async () => void t.result.current.closeMember())
    expect(t.result.current.state.open).toBeNull()
  })

  it('switches an account off, says what went with it, and leaves the row where it was', async () => {
    const t = mount(useAdminMembers, {
      ...asAdmin,
      loadMembers: jest.fn(async () => ok([member(4)])),
      removeMember: jest.fn(async () => ok(2)),
    })
    await flush()
    await load(t.result.current.refresh)
    let done: boolean | undefined
    await act(async () => {
      done = await t.result.current.remove(4, 'spam')
    })
    expect(done).toBe(true)
    expect(t.result.current.state.notice).toBe('Switched off · 2 devices signed out.')
    expect(t.result.current.state.open).toBeNull()
    expect(t.result.current.state.members[0]?.deactivatedAt).not.toBeNull()
  })

  it('says nothing happened when the node refused, and keeps the sheet open to be tried again', async () => {
    const t = mount(useAdminMembers, {
      ...asAdmin,
      loadMembers: jest.fn(async () => ok([member(4)])),
      loadMember: jest.fn(async () => ok({ member: member(4), history: [] })),
      removeMember: jest.fn(async () => failed('not-an-admin')),
    })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.openMember(4)))
    let done: boolean | undefined
    await act(async () => {
      done = await t.result.current.remove(4, 'spam')
    })
    expect(done).toBe(false)
    expect(t.result.current.state.notice).toBeNull()
    expect(t.result.current.state.open).not.toBeNull()
    expect(t.result.current.state.members[0]?.deactivatedAt).toBeNull()
    expect(t.result.current.state.problem).toBe('This node only shows that to its admins.')
  })

  it('says what a refused switch-off was, rather than queue words about it', async () => {
    const t = mount(useAdminMembers, {
      ...asAdmin,
      loadMembers: jest.fn(async () => ok([member(4)])),
      loadMember: jest.fn(async () => ok({ member: member(4), history: [] })),
      removeMember: jest.fn(async () => failed('already-decided')),
    })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.remove(4, 'spam')))
    expect(t.result.current.state.problem).toBe('That account is already off, or it belongs to an admin.')
    expect(t.result.current.state.members[0]?.deactivatedAt).toBeNull()
  })
})

describe('useAdminInvites', () => {
  it('lists the links and keeps the node address for the ones that came back without a link', async () => {
    const t = mount(useAdminInvites, { ...atNode, loadInvites: jest.fn(async () => ok([invite(1), invite(2)])) })
    await flush()
    await load(t.result.current.refresh)
    expect(t.result.current.state.invites.map((i) => i.id)).toEqual([1, 2])
    expect(t.result.current.state.serverUrl).toBe('https://relay.example/api')
  })

  it('puts the link that was just made at the front, ready to be handed over', async () => {
    const issueInvite = jest.fn(async () => ok(invite(9, { note: 'for Nadia' })))
    const t = mount(useAdminInvites, { ...atNode, loadInvites: jest.fn(async () => ok([invite(1)])), issueInvite })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.issue('for Nadia')))
    expect(issueInvite).toHaveBeenCalledWith({ note: 'for Nadia' })
    expect(t.result.current.state.invites.map((i) => i.id)).toEqual([9, 1])
    expect(t.result.current.state.fresh?.id).toBe(9)
  })

  it('reads the list again and puts the fresh link away with it', async () => {
    const t = mount(useAdminInvites, { ...atNode, loadInvites: jest.fn(async () => ok([invite(9)])), issueInvite: jest.fn(async () => ok(invite(9))) })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.issue('')))
    await load(t.result.current.refresh)
    expect(t.result.current.state.fresh).toBeNull()
  })

  it('greys a link out at once and brings it back when the node refuses', async () => {
    const t = mount(useAdminInvites, { ...atNode, loadInvites: jest.fn(async () => ok([invite(1)])), revokeInvite: jest.fn(async () => failed('already-decided')) })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.revoke(1)))
    expect(t.result.current.state.invites[0]?.state).toBe('open')
    expect(t.result.current.state.problem).toBe('That link is already spent.')
  })

  it('keeps a link taken back once the node agreed', async () => {
    const t = mount(useAdminInvites, {
      ...atNode,
      loadInvites: jest.fn(async () => ok([invite(1)])),
      revokeInvite: jest.fn(async () => ok(invite(1, { state: 'revoked' }))),
    })
    await flush()
    await load(t.result.current.refresh)
    await act(async () => void (await t.result.current.revoke(1)))
    expect(t.result.current.state.invites[0]?.state).toBe('revoked')
    expect(t.result.current.state.problem).toBeNull()
  })
})
