import type { AdminError, AdminMember, MemberDetail, MemberRepository, Result } from '../domain'

type Deps = { readonly memberRepository: MemberRepository }

/** Every account on the node, newest first. `from` skips that many for the next page. */
export const makeLoadMembers =
  ({ memberRepository }: Deps) =>
  async ({ from = 0 }: { from?: number } = {}): Promise<Result<readonly AdminMember[], AdminError>> =>
    memberRepository.list(from)

/** An account and the trail that names it. */
export const makeLoadMember =
  ({ memberRepository }: Deps) =>
  async ({ id }: { id: number }): Promise<Result<MemberDetail, AdminError>> => memberRepository.detail(id)

/** Switches an account off; answers how many sessions went with it. */
export const makeRemoveMember =
  ({ memberRepository }: Deps) =>
  async ({ id, reason }: { id: number; reason: string }): Promise<Result<number, AdminError>> =>
    memberRepository.remove(id, reason)
