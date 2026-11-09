import {
  REACTION_EMOJIS,
  addReaction,
  appendPage,
  bufferPost,
  charsLeft,
  mergeReaction,
  myReaction,
  prependPosts,
  removePost,
  removeReaction,
  timeAgo,
  toggleReaction,
  validatePostBody,
  type Post,
  type Reaction,
} from '..'

const tally = (emoji: string, count: number, mine = false): Reaction => ({ emoji, count, mine })

const post = (id: string): Post => ({
  id,
  author: { id: 'u', name: 'n' },
  body: id,
  createdAt: '2026-10-29T12:00:00Z',
  locationCell: null,
  parentId: null,
  reactions: [],
  replyCount: 0,
})

describe('feed list helpers', () => {
  it('appends an older page without duplicates', () => {
    expect(appendPage([post('a'), post('b')], [post('b'), post('c')]).map((p) => p.id)).toEqual(['a', 'b', 'c'])
  })

  it('prepends new posts ahead of the list and skips known ones', () => {
    expect(prependPosts([post('a')], [post('n2'), post('a'), post('n1')]).map((p) => p.id)).toEqual(['n2', 'n1', 'a'])
  })

  it('buffers streamed posts newest first without duplicates', () => {
    const buffer = bufferPost(bufferPost([], post('1')), post('2'))
    expect(bufferPost(buffer, post('1')).map((p) => p.id)).toEqual(['2', '1'])
  })

  it('takes a post out when the stream says it is gone', () => {
    expect(removePost([post('a'), post('b')], 'a').map((p) => p.id)).toEqual(['b'])
    expect(removePost([post('a')], 'gone').map((p) => p.id)).toEqual(['a'])
  })
})

describe('reactions', () => {
  const withReactions = (...reactions: Reaction[]): Post => ({ ...post('a'), reactions })

  it('only counts an emoji that you left', () => {
    const a = withReactions(tally('👍', 3), tally('🔥', 1, true))
    expect(myReaction(a, '🔥')).toEqual(tally('🔥', 1, true))
    expect(myReaction(a, '👍')).toBeNull()
    expect(myReaction(a, '🎉')).toBeNull()
  })

  it('starts a tally nobody left and bumps one others left', () => {
    expect(addReaction([], '👍')).toEqual([tally('👍', 1, true)])
    expect(addReaction([tally('👍', 3)], '👍')).toEqual([tally('👍', 4, true)])
  })

  it('leaves an emoji alone when you already left it', () => {
    const reactions = [tally('👍', 3, true)]
    expect(addReaction(reactions, '👍')).toEqual(reactions)
  })

  it('takes your emoji back, and keeps the tally when others left it too', () => {
    expect(removeReaction([tally('👍', 3, true)], '👍')).toEqual([tally('👍', 2, false)])
    expect(removeReaction([tally('👍', 1, true)], '👍')).toEqual([])
    expect(removeReaction([tally('👍', 3)], '👍')).toEqual([tally('👍', 3)])
  })

  it('keeps what the server counted for one emoji, and drops one it says is empty', () => {
    expect(mergeReaction([tally('👍', 1), tally('🔥', 2)], tally('👍', 9, true))).toEqual([
      tally('👍', 9, true),
      tally('🔥', 2),
    ])
    expect(mergeReaction([tally('👍', 1)], tally('🔥', 2, true))).toEqual([tally('👍', 1), tally('🔥', 2, true)])
    expect(mergeReaction([tally('👍', 1, true)], tally('👍', 0, false))).toEqual([])
  })

  it('toggles one emoji on a post and back off again', () => {
    const left = toggleReaction(post('a'), '❤️')
    expect(left.reactions).toEqual([tally('❤️', 1, true)])
    expect(toggleReaction(left, '❤️').reactions).toEqual([])
  })

  it('offers the six emojis the picker shows', () => {
    expect(REACTION_EMOJIS).toEqual(['👍', '❤️', '😂', '😮', '😢', '🔥'])
  })
})

describe('post body', () => {
  it('rejects blank and over-long bodies', () => {
    expect(validatePostBody('   ')).toBe('empty')
    expect(validatePostBody('x'.repeat(501))).toBe('too-long')
    expect(validatePostBody('x'.repeat(500))).toBeNull()
  })

  it('counts the characters left', () => {
    expect(charsLeft('x'.repeat(112))).toBe(388)
  })
})

describe('timeAgo', () => {
  const now = new Date('2026-10-29T12:00:00Z')
  it.each([
    ['2026-10-29T11:59:50Z', 'just now'],
    ['2026-10-29T11:55:00Z', '5 min ago'],
    ['2026-10-29T11:00:00Z', '1 h ago'],
    ['2026-10-26T12:00:00Z', '3 d ago'],
    ['2026-08-01T12:00:00Z', '2026-08-01'],
    ['garbage', ''],
  ])('%s -> %s', (iso, expected) => {
    expect(timeAgo(iso, now)).toBe(expected)
  })
})
