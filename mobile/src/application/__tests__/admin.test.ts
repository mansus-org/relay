import { err, ok, type AdminMember, type AdminError, type Invite, type MemberRepository, type ModeratedPost, type ModerationRepository, type InviteRepository } from '../../domain'
import { makeLoadMember, makeLoadMembers, makeRemoveMember } from '../members'
import { makeLoadInvites, makeIssueInvite, makeRevokeInvite } from '../invites'
import { makeLoadModeratedPost, makeLoadQueue, makeReviewPost } from '../moderation'

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

const member = (id: number): AdminMember => ({
  id,
  name: `Member ${id}`,
  handle: `member${id}`,
  joinedAt: '2025-03-12T10:00:00',
  isAdmin: false,
  deactivatedAt: null,
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

const refused = (error: AdminError) => err<AdminError>(error)

const moderation = (overrides: Partial<ModerationRepository> = {}): ModerationRepository => ({
  queue: async () => ok([]),
  get: async (id) => ok(post(id)),
  review: async () => ok('approved'),
  ...overrides,
})

const members = (overrides: Partial<MemberRepository> = {}): MemberRepository => ({
  list: async () => ok([]),
  detail: async (id) => ok({ member: member(id), history: [] }),
  remove: async () => ok(0),
  ...overrides,
})

const invites = (overrides: Partial<InviteRepository> = {}): InviteRepository => ({
  list: async () => ok([]),
  issue: async () => ok(invite(1)),
  revoke: async (id) => ok(invite(id, { state: 'revoked' })),
  ...overrides,
})

describe('the queue', () => {
  it('is whatever the node says is waiting', async () => {
    const loadQueue = makeLoadQueue({ moderationRepository: moderation({ queue: async () => ok([post('p2'), post('p1')]) }) })
    expect(await loadQueue()).toEqual({ ok: true, value: [post('p2'), post('p1')] })
  })

  it('passes the refusal through without dressing it up', async () => {
    const loadQueue = makeLoadQueue({ moderationRepository: moderation({ queue: async () => refused('not-an-admin') }) })
    expect(await loadQueue()).toEqual({ ok: false, error: 'not-an-admin' })
  })

  it('reads one post whole, in whatever state it is in now', async () => {
    const get = jest.fn(async (id: string) => ok(post(id, { status: 'removed' })))
    const load = makeLoadModeratedPost({ moderationRepository: moderation({ get }) })
    expect(await load({ id: 'p1' })).toEqual({ ok: true, value: post('p1', { status: 'removed' }) })
    expect(get).toHaveBeenCalledWith('p1')
  })

  it('sends the reason along with a removal, and an empty one when nothing was written', async () => {
    const review = jest.fn(async () => ok('removed' as const))
    const reviewPost = makeReviewPost({ moderationRepository: moderation({ review }) })
    await reviewPost({ id: 'p1', action: 'remove', reason: 'contact details' })
    await reviewPost({ id: 'p2', action: 'approve' })
    expect(review.mock.calls).toEqual([
      ['p1', 'remove', 'contact details'],
      ['p2', 'approve', ''],
    ])
  })

  it('reports what the node ended up deciding, which is not always what was asked for', async () => {
    const reviewPost = makeReviewPost({ moderationRepository: moderation({ review: async () => refused('already-decided') }) })
    expect(await reviewPost({ id: 'p1', action: 'approve' })).toEqual({ ok: false, error: 'already-decided' })
  })
})

describe('the members', () => {
  it('reads a page of accounts from wherever the last one stopped', async () => {
    const list = jest.fn(async (from = 0) => ok([member(from + 1)]))
    const loadMembers = makeLoadMembers({ memberRepository: members({ list }) })
    expect(await loadMembers()).toEqual({ ok: true, value: [member(1)] })
    expect(await loadMembers({ from: 50 })).toEqual({ ok: true, value: [member(51)] })
    expect(list.mock.calls).toEqual([[0], [50]])
  })

  it('reads an account with the trail that names it', async () => {
    const detail = jest.fn(async (id: number) => ok({ member: member(id), history: [] }))
    const loadMember = makeLoadMember({ memberRepository: members({ detail }) })
    expect(await loadMember({ id: 7 })).toEqual({ ok: true, value: { member: member(7), history: [] } })
    expect(detail).toHaveBeenCalledWith(7)
  })

  it('answers how many devices a switch off signed out', async () => {
    const remove = jest.fn(async () => ok(3))
    const removeMember = makeRemoveMember({ memberRepository: members({ remove }) })
    expect(await removeMember({ id: 4, reason: 'spam' })).toEqual({ ok: true, value: 3 })
    expect(remove).toHaveBeenCalledWith(4, 'spam')
  })

  it('refuses to pretend an account was switched off when the node said no', async () => {
    const removeMember = makeRemoveMember({ memberRepository: members({ remove: async () => refused('not-an-admin') }) })
    expect(await removeMember({ id: 4, reason: 'spam' })).toEqual({ ok: false, error: 'not-an-admin' })
  })
})

describe('the invites', () => {
  it('reads the links a node handed out, a page at a time', async () => {
    const list = jest.fn(async (from = 0) => ok([invite(from + 1)]))
    const loadInvites = makeLoadInvites({ inviteRepository: invites({ list }) })
    await loadInvites()
    await loadInvites({ from: 50 })
    expect(list.mock.calls).toEqual([[0], [50]])
  })

  it('keeps who a link is for, and sends nothing when nobody wrote it down', async () => {
    const issue = jest.fn(async () => ok(invite(1)))
    const issueInvite = makeIssueInvite({ inviteRepository: invites({ issue }) })
    await issueInvite({ note: '  for Nadia  ' })
    await issueInvite({ note: '   ' })
    expect(issue.mock.calls).toEqual([['for Nadia'], [null]])
  })

  it('takes back a link that is still open', async () => {
    const revoke = jest.fn(async (id: number) => ok(invite(id, { state: 'revoked' })))
    const revokeInvite = makeRevokeInvite({ inviteRepository: invites({ revoke }) })
    expect(await revokeInvite({ id: 2 })).toEqual({ ok: true, value: invite(2, { state: 'revoked' }) })
    expect(revoke).toHaveBeenCalledWith(2)
  })

  it('says so when the link was already spent', async () => {
    const revokeInvite = makeRevokeInvite({ inviteRepository: invites({ revoke: async () => refused('already-decided') }) })
    expect(await revokeInvite({ id: 2 })).toEqual({ ok: false, error: 'already-decided' })
  })
})
