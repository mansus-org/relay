import type { AdminError, ModeratedPost, ModerationDecision, ModerationRepository, Result, ReviewAction } from '../domain'

type Deps = { readonly moderationRepository: ModerationRepository }

/** What is waiting for a decision, newest first. */
export const makeLoadQueue =
  ({ moderationRepository }: Deps) =>
  async (): Promise<Result<readonly ModeratedPost[], AdminError>> => moderationRepository.queue()

/** One post whole, in whatever state it is in now - the queue only ever lists one state at a time. */
export const makeLoadModeratedPost =
  ({ moderationRepository }: Deps) =>
  async ({ id }: { id: string }): Promise<Result<ModeratedPost, AdminError>> => moderationRepository.get(id)

/** Approve or remove a post. The node answers with what it ended up being, which is not always what was asked for. */
export const makeReviewPost =
  ({ moderationRepository }: Deps) =>
  async ({ id, action, reason = '' }: { id: string; action: ReviewAction; reason?: string }): Promise<
    Result<ModerationDecision, AdminError>
  > => moderationRepository.review(id, action, reason)
