import { useCallback, useEffect, useState } from 'react'

import { adminErrorMessage, type AdminError, type Invite } from '../domain'
import { useUseCases } from './use-cases'

/** How many invites are read at a time. */
const PAGE = 50

/** The one refusal an invite ever gets is that the link is already spent, and that is worth saying
 * in its own words - "somebody got there first" belongs to the queue, not to a link. */
const inviteProblem = (error: AdminError): string =>
  error === 'already-decided' ? 'That link is already spent.' : adminErrorMessage(error)

export type InvitesState = {
  /** False until the first read comes back. */
  loaded: boolean
  invites: readonly Invite[]
  /** There may be more past what is on screen. */
  more: boolean
  loadingMore: boolean
  /** A new link is on its way. */
  issuing: boolean
  /** The invite whose "take back" is on its way. */
  revoking: number | null
  /** The link that was just made, kept up front so it can be copied before the list buries it. */
  fresh: Invite | null
  /** The node's own address, for the case where an invite came back without a link to send. */
  serverUrl: string
  problem: string | null
}

const initial: InvitesState = {
  loaded: false,
  invites: [],
  more: false,
  loadingMore: false,
  issuing: false,
  revoking: null,
  fresh: null,
  serverUrl: '',
  problem: null,
}

/**
 * The links that let people in, and the two things that change one: handing it out, taking it back.
 *
 * Taking one back is shown at once and walked back when the node refuses - which it does for a link
 * somebody already used, and that is worth saying out loud, because it means the person is already
 * in. The link that was just made stays on top of the list until the list is read again.
 */
export function useAdminInvites() {
  const { loadInvites, issueInvite, revokeInvite, readServerUrl } = useUseCases()
  const [state, setState] = useState<InvitesState>(initial)

  const refresh = useCallback(async () => {
    // Reading the list again is also what puts the fresh link away: it is on screen to be handed
    // over now, not to be kept under the list forever.
    setState((s) => ({ ...s, problem: null, fresh: null }))
    const result = await loadInvites({ from: 0 })
    setState((s) => ({
      ...s,
      loaded: true,
      invites: result.ok ? result.value : s.invites,
      more: result.ok ? result.value.length === PAGE : s.more,
      problem: result.ok ? s.problem : inviteProblem(result.error),
    }))
  }, [loadInvites])

  // The link an admin sends has to name a node. When the deployment said what host it is on, the
  // invite already carries that; when it did not, this app's own address is the honest answer.
  useEffect(() => {
    void readServerUrl().then((serverUrl) => setState((s) => ({ ...s, serverUrl })))
  }, [readServerUrl])

  const loadMore = useCallback(async () => {
    setState((s) => ({ ...s, loadingMore: true }))
    const result = await loadInvites({ from: state.invites.length })
    setState((s) => ({
      ...s,
      loadingMore: false,
      invites: result.ok ? [...s.invites, ...result.value] : s.invites,
      more: result.ok ? result.value.length === PAGE : s.more,
      problem: result.ok ? s.problem : inviteProblem(result.error),
    }))
  }, [loadInvites, state.invites.length])

  /** Hands out a link; the note says who it is for. False when the node would not make one. */
  const issue = useCallback(
    async (note: string) => {
      setState((s) => ({ ...s, issuing: true, problem: null }))
      const result = await issueInvite({ note })
      if (!result.ok) {
        setState((s) => ({ ...s, issuing: false, problem: inviteProblem(result.error) }))
        return false
      }
      setState((s) => ({ ...s, issuing: false, fresh: result.value, invites: [result.value, ...s.invites] }))
      return true
    },
    [issueInvite],
  )

  /** Takes back a link nobody has used. The card goes grey at once and comes back if the node refuses. */
  const revoke = useCallback(
    async (id: number) => {
      const before = state.invites
      const now = new Date().toISOString()
      setState((s) => ({
        ...s,
        revoking: id,
        problem: null,
        invites: s.invites.map((invite) => (invite.id === id ? { ...invite, state: 'revoked' as const, revokedAt: now } : invite)),
      }))
      const result = await revokeInvite({ id })
      setState((s) => ({
        ...s,
        revoking: null,
        invites: result.ok ? s.invites.map((invite) => (invite.id === id ? result.value : invite)) : before,
        problem: result.ok ? s.problem : inviteProblem(result.error),
      }))
    },
    [revokeInvite, state.invites],
  )

  return { state, refresh, loadMore, issue, revoke }
}
