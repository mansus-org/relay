/**
 * Running a node: the queue of posts that need a decision, the accounts on the node, and the
 * invites that let anybody in at all.
 *
 * None of this reaches an ordinary member. Every route under `/admin` answers 403 unless the
 * token belongs to an account marked as an admin, which is why the screens that read these
 * types hang off one row on Settings that only admins can see.
 */
import type { ApiError } from './post'

/** Where a post stands with moderation. */
export type ModerationDecision = 'pending' | 'approved' | 'removed'

/** What an admin can ask the node to do about a post from the queue. */
export type ReviewAction = 'approve' | 'remove'

/**
 * What can go wrong on an admin call.
 *
 * `already-decided` is the one that happens in practice: two admins looking at the same queue
 * will reach for the same card, and the node refuses the second hand rather than logging the
 * same decision twice.
 */
export type AdminError = ApiError | 'not-an-admin' | 'not-found' | 'already-decided'

const ADMIN_MESSAGES: Record<AdminError, string> = {
  network: 'Could not reach Relay. Check your connection and try again.',
  unexpected: 'Something went wrong on the node.',
  'not-an-admin': 'This node only shows that to its admins.',
  'not-found': 'That is not on this node any more.',
  'already-decided': 'Somebody got there first. Pull to see the queue again.',
}

export const adminErrorMessage = (error: AdminError): string => ADMIN_MESSAGES[error]

// --- what a model said ----------------------------------------------------------------


/**
 * What a model said about a post, in the machine's own words.
 *
 * The node passes this through without explaining it, and nothing writes one yet: the sidecar
 * that screens posts has not landed. So the shape belongs to whoever writes the model, and the
 * reader here looks for the three things an admin needs off a badge - what it decided, how sure
 * it was, and the sentence it gave - under any of the names a model's author is likely to pick.
 * Whatever else is in the JSON is still shown, on the post's own page, rather than dropped.
 */
export type AiDecision = Readonly<Record<string, unknown>>

export type AiVerdict = 'approved' | 'flagged' | 'removed'

const VERDICT_KEYS = ['verdict', 'decision', 'action', 'label', 'status'] as const
const CONFIDENCE_KEYS = ['confidence', 'score', 'probability', 'p'] as const
const REASON_KEYS = ['reason', 'rationale', 'explanation', 'why', 'note'] as const

const VERDICT_WORDS: Record<AiVerdict, readonly string[]> = {
  approved: ['approved', 'approve', 'allow', 'allowed', 'pass', 'passed', 'clean', 'safe', 'ok'],
  flagged: ['flagged', 'flag', 'review', 'hold', 'held', 'uncertain', 'unsure', 'maybe'],
  removed: ['removed', 'remove', 'blocked', 'block', 'rejected', 'reject', 'spam', 'violation', 'fail'],
}

/** Loose on purpose: the words are the model's, and a model says "spam" as often as "removed". */
export const aiVerdict = (ai: AiDecision | null): AiVerdict | null => {
  if (!ai) return null
  let word = ''
  for (const key of VERDICT_KEYS) {
    const value = ai[key]
    if (typeof value === 'string' && value.trim() !== '') {
      word = value.trim().toLowerCase()
      break
    }
  }
  if (!word) return null
  const verdicts = Object.keys(VERDICT_WORDS) as AiVerdict[]
  for (const verdict of verdicts) if (VERDICT_WORDS[verdict].includes(word)) return verdict
  for (const verdict of verdicts) if (VERDICT_WORDS[verdict].some((one) => word.includes(one))) return verdict
  return null
}

/** How sure the model was, as a whole percent. It may answer 0.92 or 92; both mean ninety-two. */
export const aiConfidence = (ai: AiDecision | null): number | null => {
  if (!ai) return null
  for (const key of CONFIDENCE_KEYS) {
    const value = ai[key]
    const number = typeof value === 'string' ? Number(value) : value
    if (typeof number === 'number' && Number.isFinite(number) && number >= 0) {
      return Math.round(number > 0 && number <= 1 ? number * 100 : number)
    }
  }
  return null
}

/** The sentence the model gave, when it gave one. */
export const aiReason = (ai: AiDecision | null): string | null => {
  if (!ai) return null
  for (const key of REASON_KEYS) {
    const value = ai[key]
    if (typeof value === 'string' && value.trim() !== '') return value.trim()
  }
  return null
}

export type AiBadge = { readonly label: string; readonly tone: 'ok' | 'warn' | 'bad' }

/** The chip over a card: `flagged 82%`. Null means no model has looked, which is not the same
 * as one that looked and found nothing, so the card says nothing rather than "clean". */
export const aiBadge = (ai: AiDecision | null): AiBadge | null => {
  const verdict = aiVerdict(ai)
  if (!verdict) return null
  const confidence = aiConfidence(ai)
  const tone = verdict === 'approved' ? 'ok' : verdict === 'flagged' ? 'warn' : 'bad'
  return {
    label: confidence === null ? verdict : `${verdict} ${confidence}%`,
    tone,
  }
}

/** The parts of the machine's answer that the badge and the reason did not already say. */
export const aiRest = (ai: AiDecision | null): readonly { readonly key: string; readonly value: string }[] => {
  if (!ai) return []
  const shown: ReadonlySet<string> = new Set([...VERDICT_KEYS, ...CONFIDENCE_KEYS, ...REASON_KEYS])
  return Object.entries(ai)
    .filter(([key, value]) => !shown.has(key) && value !== null && value !== undefined)
    .map(([key, value]) => ({ key, value: typeof value === 'string' ? value : JSON.stringify(value) }))
}

// --- the queue ------------------------------------------------------------------------


/** One post as moderation sees it: the whole body, and where it stands. */
export type ModeratedPost = {
  readonly id: string
  readonly body: string
  readonly createdAt: string
  readonly authorId: string
  readonly status: ModerationDecision
  readonly communityId: string | null
  readonly parentId: string | null
  readonly ai: AiDecision | null
}

/**
 * The name the queue has to offer for a post's author.
 *
 * The queue carries an `author_id` and nothing on the node joins that UUID to an account row -
 * the backend says so out loud rather than guessing at a join between two id types. Eight
 * characters tells two members apart to somebody who already knows them; it cannot name them.
 */
export const authorLabel = (authorId: string): string => `Member ${authorId.slice(0, 8)}`

// --- the members ----------------------------------------------------------------------


/** One account on the node, and whether it is still allowed to be one. */
export type AdminMember = {
  readonly id: number
  readonly name: string
  readonly handle: string
  readonly joinedAt: string
  readonly isAdmin: boolean
  readonly deactivatedAt: string | null
}

/** One line of the trail: what moderation did, and who did it. */
export type ModerationLogEntry = {
  readonly id: number
  readonly action: string
  readonly trigger: string
  readonly reason: string
  readonly createdAt: string
  readonly postId: string | null
  readonly targetUserId: number | null
}

/** An account, and everything moderation already did to it. */
export type MemberDetail = {
  readonly member: AdminMember
  readonly history: readonly ModerationLogEntry[]
}

/**
 * Whether this admin is allowed to try. The node refuses its own account and every other
 * admin's, so the button is not offered for them.
 */
export const canRemoveMember = (member: AdminMember, myHandle: string): boolean =>
  !member.isAdmin && member.handle.toLowerCase() !== myHandle.toLowerCase()

const LOG_WORDS: Record<string, string> = {
  approved: 'Approved a post',
  removed: 'Removed a post',
  restored: 'Put a post back',
  flagged: 'Flagged a post',
  member_deactivated: 'Switched this account off',
  member_restored: 'Put this account back',
}

/** What a line of the trail says, in the few words a sheet has room for. */
export const logEntryLabel = (entry: ModerationLogEntry): string => {
  const who = entry.trigger === 'ai' ? 'the model' : 'an admin'
  const what = LOG_WORDS[entry.action] ?? entry.action
  return `${what} · ${who}${entry.reason === '' ? '' : ` — ${entry.reason}`}`
}

// --- the invites ----------------------------------------------------------------------


/** Open is still waiting to be redeemed; the other two are spent. */
export type InviteState = 'open' | 'used' | 'revoked'

export type Invite = {
  readonly id: number
  readonly token: string
  readonly url: string | null
  readonly note: string | null
  readonly state: InviteState
  readonly createdAt: string | null
  readonly usedAt: string | null
  readonly usedById: number | null
  readonly revokedAt: string | null
}

/**
 * The link to send somebody.
 *
 * The node assembles it when the deployment said what host it is on, and says nothing when it
 * did not. This app's own server is the honest answer in that case: the invite came from that
 * node, so a link to it is the link that works.
 */
export const inviteLink = (invite: Invite, serverUrl: string): string => {
  if (invite.url) return invite.url
  const root = serverUrl.trim().replace(/\/+$/, '')
  return `${root}/join?token=${encodeURIComponent(invite.token)}`
}

/** Only the first of an invite's states is still usable, and only that one can be revoked. */
export const canRevokeInvite = (invite: Invite): boolean => invite.state === 'open'

/** The token shortened for a row. The whole thing is on the sheet, and nowhere else. */
export const tokenPreview = (token: string): string => (token.length > 12 ? `${token.slice(0, 12)}…` : token)

/** The word on the state box. An open invite is called `pending` there, because that is what it
 * is waiting for; the node's own word for the state is `active`. */
export const inviteStateLabel = (invite: Invite): string =>
  invite.state === 'open' ? 'pending' : invite.state === 'used' ? 'used' : 'revoked'

/** "today", "yesterday", or the month - whichever is the more useful thing to say. */
const dayOrMonth = (iso: string | null): string => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const days = Math.floor((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return monthYear(iso)
}

/** A row's second line. The node gives `used_by` as an id with no handle next to it, so a used
 * invite says when it went and not to whom; naming them would mean guessing at an id. */
export const inviteSubline = (invite: Invite): string => {
  if (invite.state === 'used') return invite.usedAt ? `Used ${monthYear(invite.usedAt)}` : 'Used'
  if (invite.state === 'revoked') return invite.revokedAt ? `Revoked ${monthYear(invite.revokedAt)}` : 'Revoked'
  const when = dayOrMonth(invite.createdAt)
  return when === '' ? 'Invite' : `Created ${when}`
}

// --- dates ----------------------------------------------------------------------------


const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const

const pad = (n: number): string => (n < 10 ? `0${n}` : `${n}`)

/** "Mar 12, 2025" — the day an account joined. */
export const dayMonthYear = (iso: string | null): string => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
}

/** "Sep 2025" — the month an account joined or an invite was handed out. */
export const monthYear = (iso: string | null): string => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${MONTHS[date.getMonth()]} ${date.getFullYear()}`
}

/** "3 Oct 2026, 14:05" — when a decision was made, to the minute it was made. */
export const dateTime = (iso: string | null): string => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}, ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
