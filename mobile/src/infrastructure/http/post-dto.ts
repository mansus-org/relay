import type { Post } from '../../domain'

export type PostDto = {
  id: string
  author: { id: string; name: string }
  body: string
  created_at: string
  location_cell?: string | null
  reactions?: { emoji: string; count: number; mine?: boolean }[]
  reply_count?: number
}

export const toPost = (dto: PostDto): Post => ({
  id: dto.id,
  author: { id: dto.author.id, name: dto.author.name },
  body: dto.body,
  createdAt: dto.created_at,
  locationCell: dto.location_cell ?? null,
  reactions: (dto.reactions ?? []).map((r) => ({ emoji: r.emoji, count: r.count, mine: r.mine ?? false })),
  replyCount: dto.reply_count ?? 0,
})
