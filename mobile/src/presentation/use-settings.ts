import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'expo-router'

import type { AuthError, NodeError, NodeTest, Profile } from '../domain'
import { useAuth } from './auth'
import { useUseCases } from './use-cases'

export type SettingsState = {
  /** False until the account has been read, or failed to. */
  loaded: boolean
  profile: Profile | null
  /** Nobody could be read: signed out, or the node refused the token. */
  failed: boolean
  /** The node this app points at, as stored. */
  serverUrl: string
  /** The last test run, whatever address it was run against. */
  test: NodeTest | null
  testing: boolean
  moving: boolean
  /** Why a node was refused, in the words the sheet shows. */
  nodeError: string | null
  renaming: boolean
  /** Why a name was refused, in the words the sheet shows. */
  nameError: string | null
}

const initial: SettingsState = {
  loaded: false,
  profile: null,
  failed: false,
  serverUrl: '',
  test: null,
  testing: false,
  moving: false,
  nodeError: null,
  renaming: false,
  nameError: null,
}

const NODE_ERROR: Record<NodeError, string> = {
  'bad-url': 'That address is not one Relay can read.',
  unreachable: 'That server did not answer. Nothing was changed.',
}

const NAME_ERROR: Record<AuthError, string> = {
  'invalid-credentials': 'That is not the account on this server.',
  'invalid-invite': 'That invite will not work.',
  'username-taken': 'That handle is taken.',
  'invalid-name': 'That name is not one this server will keep.',
  'no-session': 'You are not signed in here.',
  gone: 'That account is not on this server any more.',
  network: 'The server did not answer.',
  unexpected: 'The server did not answer.',
}

/**
 * The account and the node it lives on: who you are here, the name you go by, whether another
 * node answers, and the move that signs you out. Every sentence a failure produces is decided
 * here, so the screen only has to show it.
 */
export function useSettings() {
  const { getProfile, updateProfile, testNode, switchNode, readServerUrl } = useUseCases()
  const { renamed, logout } = useAuth()
  const router = useRouter()
  const [state, setState] = useState<SettingsState>(initial)

  const patch = useCallback((next: Partial<SettingsState>) => setState((s) => ({ ...s, ...next })), [])

  useEffect(() => {
    // The first read is what the row and the header are waiting on, so both are fetched at once.
    void (async () => {
      const [serverUrl, result] = await Promise.all([readServerUrl(), getProfile()])
      patch(
        result.ok
          ? { loaded: true, serverUrl, profile: result.value, failed: false }
          : { loaded: true, serverUrl, profile: null, failed: true },
      )
    })()
  }, [readServerUrl, getProfile, patch])

  const test = useCallback(
    async (url: string) => {
      patch({ testing: true, nodeError: null })
      const result = await testNode(url)
      patch({ testing: false, test: result.ok ? result.value : null, nodeError: result.ok ? null : NODE_ERROR[result.error] })
    },
    [patch, testNode],
  )

  /**
   * Move to another node. The session goes with the move, because a token one node minted means
   * nothing at the next one, so this ends the visit: the sheet closes and the sign-in screen is
   * the next thing you see.
   */
  const move = useCallback(
    async (url: string) => {
      patch({ moving: true, nodeError: null })
      const result = await switchNode(url)
      patch({ moving: false })
      if (!result.ok) return patch({ nodeError: NODE_ERROR[result.error] })
      setState({ ...initial, loaded: true, serverUrl: result.value })
      await logout()
      router.replace('/login')
    },
    [patch, router, switchNode, logout],
  )

  const rename = useCallback(
    async (displayName: string) => {
      patch({ renaming: true, nameError: null })
      const result = await updateProfile(displayName)
      patch({ renaming: false })
      if (!result.ok) return patch({ nameError: NAME_ERROR[result.error] })
      patch({ profile: result.value })
      // The header avatar reads the session, and the session does not know yet.
      renamed(result.value.displayName)
    },
    [patch, renamed, updateProfile],
  )

  return { state, test, move, rename }
}
