import type { AdminError, Invite, InviteRepository, Result } from '../domain'

type Deps = { readonly inviteRepository: InviteRepository }

/** Every invite this node has handed out, newest first, whoever it went to. */
export const makeLoadInvites =
  ({ inviteRepository }: Deps) =>
  async ({ from = 0 }: { from?: number } = {}): Promise<Result<readonly Invite[], AdminError>> =>
    inviteRepository.list(from)

/** Hands out a link. Whatever was written about it travels with it, so the list can say who it was for. */
export const makeIssueInvite =
  ({ inviteRepository }: Deps) =>
  async ({ note }: { note: string }): Promise<Result<Invite, AdminError>> => inviteRepository.issue(note.trim() || null)

/** Takes back a link nobody has used yet. */
export const makeRevokeInvite =
  ({ inviteRepository }: Deps) =>
  async ({ id }: { id: number }): Promise<Result<Invite, AdminError>> => inviteRepository.revoke(id)
