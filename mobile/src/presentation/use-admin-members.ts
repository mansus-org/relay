import { useCallback, useEffect, useState } from 'react'

import { adminErrorMessage, type AdminMember, type MemberDetail } from '../domain'
import { useUseCases } from './use-cases'

/** How many accounts are read at a time; the node answers 50 when asked for nothing. */
const PAGE = 50

export type MembersState = {
  /** False until the first read comes back. */
  loaded: boolean
  members: readonly AdminMember[]
  /** There may be more accounts past what is on screen. */
  more: boolean
  loadingMore: boolean
  /** The account whose sheet is open, with the trail that names it. */
  open: MemberDetail | null
  /** Your own handle, once the node has said it: the sheet will not offer to switch you off. */
  myHandle: string | null
  /** That sheet is still reading the trail. */
  opening: boolean
  /** The switch is being thrown. */
  removing: boolean
  problem: string | null
  /** The last thing that worked, in the words the list shows under its heading. */
  notice: string | null
}

const initial: MembersState = {
  loaded: false,
  members: [],
  more: false,
  loadingMore: false,
  open: null,
  myHandle: null,
  opening: false,
  removing: false,
  problem: null,
  notice: null,
}

/**
 * The accounts on this node, and the one thing an admin may do to one: switch it off.
 *
 * Nobody is deleted, so nothing here pretends to be. A switched-off account keeps its row and its
 * name in every trail, and the sheet that switched it off says how many of its devices had to
 * sign in again - which is the only part of the change a person actually feels.
 */
export function useAdminMembers() {
  const { loadMembers, loadMember, removeMember, getProfile } = useUseCases()
  const [state, setState] = useState<MembersState>(initial)

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, problem: null, notice: null }))
    const result = await loadMembers({ from: 0 })
    setState((s) => ({
      ...s,
      loaded: true,
      members: result.ok ? result.value : s.members,
      more: result.ok ? result.value.length === PAGE : s.more,
      problem: result.ok ? s.problem : adminErrorMessage(result.error),
    }))
  }, [loadMembers])

  // The node will not let an admin remove themselves or a fellow admin, and it says so by refusing.
  // Reading your own handle first means the sheet never offers a button that only answers 403.
  useEffect(() => {
    void getProfile().then((result) => {
      if (result.ok) setState((s) => ({ ...s, myHandle: result.value.handle }))
    })
  }, [getProfile])

  const loadMore = useCallback(async () => {
    setState((s) => ({ ...s, loadingMore: true }))
    const result = await loadMembers({ from: state.members.length })
    setState((s) => ({
      ...s,
      loadingMore: false,
      members: result.ok ? [...s.members, ...result.value] : s.members,
      more: result.ok ? result.value.length === PAGE : s.more,
      problem: result.ok ? s.problem : adminErrorMessage(result.error),
    }))
  }, [loadMembers, state.members.length])

  /** Opens the sheet on one account. Its trail is read then, not carried for every row. */
  const openMember = useCallback(
    async (id: number) => {
      setState((s) => ({ ...s, opening: true, problem: null }))
      const result = await loadMember({ id })
      setState((s) => ({
        ...s,
        opening: false,
        open: result.ok ? result.value : null,
        problem: result.ok ? s.problem : adminErrorMessage(result.error),
      }))
    },
    [loadMember],
  )

  const closeMember = useCallback(() => setState((s) => ({ ...s, open: null })), [])

  /** Switches an account off and says what went with it. The row stays; the sheet closes. */
  const remove = useCallback(
    async (id: number, reason: string) => {
      setState((s) => ({ ...s, removing: true, problem: null }))
      const result = await removeMember({ id, reason })
      if (!result.ok) {
        setState((s) => ({ ...s, removing: false, problem: adminErrorMessage(result.error) }))
        return false
      }
      const signedOut = result.value
      setState((s) => ({
        ...s,
        removing: false,
        open: null,
        notice: signedOut > 0 ? `Switched off · ${signedOut} ${signedOut === 1 ? 'device' : 'devices'} signed out.` : 'Switched off.',
        members: s.members.map((member) => (member.id === id ? { ...member, deactivatedAt: new Date().toISOString() } : member)),
      }))
      return true
    },
    [removeMember],
  )

  return { state, refresh, loadMore, openMember, closeMember, remove }
}
