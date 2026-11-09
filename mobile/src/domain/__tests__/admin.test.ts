import {
  adminErrorMessage,
  aiBadge,
  aiConfidence,
  aiReason,
  aiRest,
  aiVerdict,
  authorLabel,
  canRemoveMember,
  canRevokeInvite,
  dayMonthYear,
  dateTime,
  inviteLink,
  inviteStateLabel,
  inviteSubline,
  logEntryLabel,
  monthYear,
  tokenPreview,
  type AdminMember,
  type Invite,
  type ModerationLogEntry,
} from '../admin'

const member = (handle: string, overrides: Partial<AdminMember> = {}): AdminMember => ({
  id: 1,
  name: 'Ada L.',
  handle,
  joinedAt: '2025-03-12T10:00:00',
  isAdmin: false,
  deactivatedAt: null,
  ...overrides,
})

const invite = (overrides: Partial<Invite> = {}): Invite => ({
  id: 1,
  token: 'T3FhZmlobEl6TllQQXlHUkxnNGdKaGQ5U3RvcDJ5ZXQwcXlvMg',
  url: null,
  note: null,
  state: 'open',
  createdAt: '2025-03-12T10:00:00',
  usedAt: null,
  usedById: null,
  revokedAt: null,
  ...overrides,
})

const entry = (overrides: Partial<ModerationLogEntry> = {}): ModerationLogEntry => ({
  id: 1,
  action: 'removed',
  trigger: 'admin',
  reason: '',
  createdAt: '2025-03-12T10:00:00',
  postId: 'p1',
  targetUserId: null,
  ...overrides,
})

describe('adminErrorMessage', () => {
  it('says what an admin being refused actually means', () => {
    expect(adminErrorMessage('not-an-admin')).toBe('This node only shows that to its admins.')
    expect(adminErrorMessage('not-found')).toBe('That is not on this node any more.')
    expect(adminErrorMessage('already-decided')).toBe('Somebody got there first. Pull to see the queue again.')
    expect(adminErrorMessage('network')).toBe('Could not reach Relay. Check your connection and try again.')
  })
})

describe('aiVerdict', () => {
  it('reads the decision under whichever name the model gave it', () => {
    expect(aiVerdict({ verdict: 'approved' })).toBe('approved')
    expect(aiVerdict({ decision: 'flagged' })).toBe('flagged')
    expect(aiVerdict({ action: 'removed' })).toBe('removed')
    expect(aiVerdict({ label: 'review' })).toBe('flagged')
  })

  it('takes the words a model uses when it is not speaking the queue\'s language', () => {
    expect(aiVerdict({ verdict: 'SPAM' })).toBe('removed')
    expect(aiVerdict({ verdict: 'needs review' })).toBe('flagged')
    expect(aiVerdict({ status: 'looks clean' })).toBe('approved')
  })

  it('says nothing when there is no decision to read', () => {
    expect(aiVerdict(null)).toBeNull()
    expect(aiVerdict({})).toBeNull()
    expect(aiVerdict({ verdict: '', confidence: 0.9 })).toBeNull()
    expect(aiVerdict({ verdict: 'something nobody named' })).toBeNull()
  })
})

describe('aiConfidence', () => {
  it('answers in whole percent whatever the model counted in', () => {
    expect(aiConfidence({ confidence: 0.92 })).toBe(92)
    expect(aiConfidence({ confidence: 92 })).toBe(92)
    expect(aiConfidence({ score: '0.8' })).toBe(80)
    expect(aiConfidence({ probability: 0 })).toBe(0)
  })

  it('says nothing when the model did not say how sure it was', () => {
    expect(aiConfidence(null)).toBeNull()
    expect(aiConfidence({ verdict: 'flagged' })).toBeNull()
    expect(aiConfidence({ confidence: -1 })).toBeNull()
    expect(aiConfidence({ confidence: 'sure' })).toBeNull()
  })
})

describe('aiReason', () => {
  it('keeps the sentence and drops everything else', () => {
    expect(aiReason({ rationale: ' Contact details in a public post. ' })).toBe('Contact details in a public post.')
    expect(aiReason({ verdict: 'flagged' })).toBeNull()
    expect(aiReason(null)).toBeNull()
  })
})

describe('aiBadge', () => {
  it('is the chip over the card: the word and how sure', () => {
    expect(aiBadge({ verdict: 'flagged', confidence: 0.82 })).toEqual({ label: 'flagged 82%', tone: 'warn' })
    expect(aiBadge({ verdict: 'approved', confidence: 0.99 })).toEqual({ label: 'approved 99%', tone: 'ok' })
    expect(aiBadge({ action: 'blocked' })).toEqual({ label: 'removed', tone: 'bad' })
  })

  it('stays off when no model has looked, which is not the same as one that found nothing', () => {
    expect(aiBadge(null)).toBeNull()
    expect(aiBadge({ model: 'relay-screener' })).toBeNull()
  })
})

describe('aiRest', () => {
  it('shows what the badge and the reason did not already say', () => {
    expect(aiRest({ verdict: 'flagged', confidence: 0.8, reason: 'spam', model: 'screener-2', categories: ['contact'] })).toEqual([
      { key: 'model', value: 'screener-2' },
      { key: 'categories', value: '["contact"]' },
    ])
    expect(aiRest(null)).toEqual([])
    expect(aiRest({ verdict: 'flagged', nothing: null })).toEqual([])
  })
})

describe('authorLabel', () => {
  it('names an author with the only part of the id the queue was given', () => {
    expect(authorLabel('a1b2c3d4-e5f6-7890-abcd-ef1234567890')).toBe('Member a1b2c3d4')
  })
})

describe('canRemoveMember', () => {
  it('will not offer to switch off your own account, however it is spelled', () => {
    expect(canRemoveMember(member('ada'), 'ada')).toBe(false)
    expect(canRemoveMember(member('Ada'), 'ada')).toBe(false)
  })

  it('will not offer it for another admin either, because the node refuses it', () => {
    expect(canRemoveMember(member('grace', { isAdmin: true }), 'ada')).toBe(false)
  })

  it('offers it for anybody else', () => {
    expect(canRemoveMember(member('bob'), 'ada')).toBe(true)
  })
})

describe('logEntryLabel', () => {
  it('says who did it, and why when there was a reason', () => {
    expect(logEntryLabel(entry())).toBe('Removed a post · an admin')
    expect(logEntryLabel(entry({ action: 'approved', reason: 'fine' }))).toBe('Approved a post · an admin — fine')
    expect(logEntryLabel(entry({ action: 'removed', trigger: 'ai', reason: 'spam' }))).toBe('Removed a post · the model — spam')
  })

  it('keeps an action it does not know rather than hiding it', () => {
    expect(logEntryLabel(entry({ action: 'renamed', reason: '' }))).toBe('renamed · an admin')
  })
})

describe('inviteLink', () => {
  it('hands over the link the node built', () => {
    expect(inviteLink(invite({ url: 'https://relay.example/join?t=abc' }), 'https://x/api')).toBe('https://relay.example/join?t=abc')
  })

  it('builds one from the node this app is pointed at when the invite came back bare', () => {
    expect(inviteLink(invite({ token: 'abc123' }), 'https://relay.example/api/')).toBe('https://relay.example/api/join?token=abc123')
    expect(inviteLink(invite({ token: 'a b/c' }), 'https://relay.example')).toBe('https://relay.example/join?token=a%20b%2Fc')
  })
})

describe('canRevokeInvite', () => {
  it('only takes back a link nobody has used yet', () => {
    expect(canRevokeInvite(invite())).toBe(true)
    expect(canRevokeInvite(invite({ state: 'used' }))).toBe(false)
    expect(canRevokeInvite(invite({ state: 'revoked' }))).toBe(false)
  })
})

describe('tokenPreview', () => {
  it('shortens a token for a row without showing the whole thing', () => {
    expect(tokenPreview('abcdefghijklmn')).toBe('abcdefghijkl…')
    expect(tokenPreview('short')).toBe('short')
  })
})

describe('inviteStateLabel', () => {
  it('calls an open invite what it is waiting for', () => {
    expect(inviteStateLabel(invite())).toBe('pending')
    expect(inviteStateLabel(invite({ state: 'used' }))).toBe('used')
    expect(inviteStateLabel(invite({ state: 'revoked' }))).toBe('revoked')
  })
})

describe('inviteSubline', () => {
  const now = new Date()
  const daysAgo = (days: number) => new Date(now.getTime() - days * 86_400_000).toISOString()

  it('says when a link went out, in the nearest useful unit', () => {
    expect(inviteSubline(invite({ createdAt: daysAgo(0) }))).toBe('Created today')
    expect(inviteSubline(invite({ createdAt: daysAgo(1) }))).toBe('Created yesterday')
    expect(inviteSubline(invite({ createdAt: daysAgo(400) }))).toBe(`Created ${monthYear(daysAgo(400))}`)
    expect(inviteSubline(invite({ createdAt: null }))).toBe('Invite')
  })

  it('says when a spent link was spent, and not to whom', () => {
    expect(inviteSubline(invite({ state: 'used', usedAt: daysAgo(3), usedById: 7 }))).toBe(`Used ${monthYear(daysAgo(3))}`)
    expect(inviteSubline(invite({ state: 'used', usedAt: null }))).toBe('Used')
    expect(inviteSubline(invite({ state: 'revoked', revokedAt: daysAgo(3) }))).toBe(`Revoked ${monthYear(daysAgo(3))}`)
  })
})

describe('dates', () => {
  it('says the day, the month, or the minute, whichever was asked for', () => {
    expect(dayMonthYear('2025-03-12T14:05:00')).toBe('Mar 12, 2025')
    expect(monthYear('2025-03-12T14:05:00')).toBe('Mar 2025')
    expect(dateTime('2025-10-03T14:05:00')).toBe('3 Oct 2025, 14:05')
    expect(dateTime('2025-10-03T04:05:00')).toBe('3 Oct 2025, 04:05')
  })

  it('says nothing about a date the node did not give', () => {
    expect(dayMonthYear(null)).toBe('')
    expect(monthYear('not a date')).toBe('')
    expect(dateTime('')).toBe('')
  })
})
