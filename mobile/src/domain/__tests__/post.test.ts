import { appendPage, bufferPost, charsLeft, prependPosts, timeAgo, validatePostBody, type Post } from '..'

const post = (id: string): Post => ({
  id,
  author: { id: 'u', name: 'n' },
  body: id,
  createdAt: '2026-10-29T12:00:00Z',
  locationCell: null,
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
