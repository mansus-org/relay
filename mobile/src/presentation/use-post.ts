import { useCallback, useEffect, useRef, useState } from 'react'

import {
  appendReply,
  dropReplies,
  insertReplies,
  mergeReaction,
  myReaction,
  removeEntry,
  replacePost,
  threadOf,
  toggleReaction as toggleReactionOnPost,
  type Post,
  type Reaction,
  type ThreadEntry,
} from '../domain'
import { useAuth } from './auth'
import { useUseCases } from './use-cases'

export type ThreadState = {
  /** False until the post itself arrives. */
  loaded: boolean
  /** The post could not be read. */
  failed: boolean
  /** The thread on screen: the post first, then whatever replies have been asked for. */
  entries: readonly ThreadEntry[]
  /** The post whose replies are being fetched, or null. */
  loadingRepliesFor: string | null
  /** A reply is being sent. */
  sending: boolean
  /** The post a reply is being written to; null when the bar is closed. */
  replyingToId: string | null
  /** What the last thing that went wrong said, or null. */
  problem: string | null
}

/** The hook's state: the thread plus the reply bar's target, resolved out of the entries. */
export type ThreadView = ThreadState & { readonly replyingTo: ThreadEntry | null }

const initial: ThreadState = {
  loaded: false,
  failed: false,
  entries: [],
  loadingRepliesFor: null,
  sending: false,
  replyingToId: null,
  problem: null,
}

const REPLIES_FAILED = 'Those replies will not load right now.'
const REPLY_FAILED = 'Your reply did not go through.'
const REACTION_FAILED = 'That reaction did not go through.'

/** Applies a change to whichever post in the thread has that id; the rest are left alone. */
const editPost = (entries: readonly ThreadEntry[], postId: string, next: (post: Post) => Post): readonly ThreadEntry[] =>
  entries.map((e) => (e.post.id === postId ? { ...e, post: next(e.post) } : e))

const withReaction = (entries: readonly ThreadEntry[], postId: string, tally: Reaction): readonly ThreadEntry[] =>
  editPost(entries, postId, (post) => ({ ...post, reactions: mergeReaction(post.reactions, tally) }))

/**
 * One thread: the post, the replies asked for so far, reactions, and the reply being written.
 *
 * Every write is put on screen as soon as it is sent and corrected when the server answers,
 * so a tap never waits on the network.
 */
export function useThread(postId: string) {
  const { loadThread, loadReplies, reply, toggleReaction: sendReaction } = useUseCases()
  const { user } = useAuth()
  const [state, setState] = useState<ThreadState>(initial)
  const pending = useRef(0)

  useEffect(() => {
    let cancelled = false
    void loadThread(postId).then((result) => {
      if (cancelled) return
      setState((s) => ({ ...s, loaded: true, failed: !result.ok, entries: result.ok ? threadOf(result.value) : s.entries }))
    })
    return () => {
      cancelled = true
    }
  }, [loadThread, postId])

  /** Shows one level of replies under a post, or hides them again. */
  const toggleReplies = useCallback(
    async (post: Post) => {
      const open = state.entries.find((e) => e.post.id === post.id)?.open
      if (open) return setState((s) => ({ ...s, entries: dropReplies(s.entries, post.id) }))
      setState((s) => ({ ...s, loadingRepliesFor: post.id, problem: null }))
      const result = await loadReplies(post.id)
      setState((s) => ({
        ...s,
        loadingRepliesFor: null,
        entries: result.ok ? insertReplies(s.entries, post.id, result.value) : s.entries,
        problem: result.ok ? s.problem : REPLIES_FAILED,
      }))
    },
    [loadReplies, state.entries],
  )

  /** Leaves an emoji on a post or takes it back, and keeps whatever the server counted. */
  const toggleReaction = useCallback(
    async (post: Post, emoji: string) => {
      const before = myReaction(post, emoji)
      setState((s) => ({ ...s, problem: null, entries: editPost(s.entries, post.id, (p) => toggleReactionOnPost(p, emoji)) }))
      const result = await sendReaction(post, emoji)
      setState((s) => ({
        ...s,
        problem: result.ok ? s.problem : REACTION_FAILED,
        entries: withReaction(s.entries, post.id, result.ok ? result.value : before ?? { emoji, count: 0, mine: false }),
      }))
    },
    [sendReaction],
  )

  /** Opens the reply bar under a post; opening another one moves it. Null closes it. */
  const askReplyTo = useCallback((postId: string | null) => {
    setState((s) => ({ ...s, replyingToId: postId, problem: null }))
  }, [])

  const cancelReply = useCallback(() => setState((s) => ({ ...s, replyingToId: null })), [])

  /** Sends a reply, shows it at once, and takes it back if the server refuses it. */
  const sendReply = useCallback(
    async (body: string): Promise<boolean> => {
      const target = state.entries.find((e) => e.post.id === state.replyingToId) ?? state.entries[0]
      if (!target || state.sending || !user) return false
      const tempId = `pending-${++pending.current}`
      const optimistic: Post = {
        id: tempId,
        author: user,
        body: body.trim(),
        createdAt: new Date().toISOString(),
        locationCell: target.post.locationCell,
        parentId: target.post.id,
        reactions: [],
        replyCount: 0,
      }
      setState((s) => ({
        ...s,
        sending: true,
        replyingToId: null,
        problem: null,
        entries: appendReply(s.entries, target.post.id, optimistic),
      }))
      const result = await reply({ parentId: target.post.id, body })
      if (result.ok) {
        setState((s) => ({ ...s, sending: false, entries: replacePost(s.entries, tempId, result.value) }))
        return true
      }
      setState((s) => ({
        ...s,
        sending: false,
        problem: REPLY_FAILED,
        // A post the reply opened for good is closed again once its reply is back off the screen.
        entries: target.open ? removeEntry(s.entries, tempId) : dropReplies(removeEntry(s.entries, tempId), target.post.id),
      }))
      return false
    },
    [reply, state.entries, state.replyingToId, state.sending, user],
  )

  const clearProblem = useCallback(() => setState((s) => ({ ...s, problem: null })), [])

  const replyingTo = state.entries.find((e) => e.post.id === state.replyingToId) ?? null
  return { state: { ...state, replyingTo }, toggleReplies, toggleReaction, askReplyTo, cancelReply, sendReply, clearProblem }
}
