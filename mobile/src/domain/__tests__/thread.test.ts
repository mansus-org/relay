import { makePost } from '../../testing/fakes'
import { appendReply, dropReplies, insertReplies, removeEntry, replacePost, threadOf, type Post, type ThreadEntry } from '..'

/** The thread as it reads on screen: each post, its depth, and a star while its replies are open. */
const shape = (entries: readonly ThreadEntry[]): string =>
  entries.map((e) => `${e.post.id}${e.depth}${e.open ? '*' : ''}`).join(' ')

const post = (id: string): Post => makePost(id)

/** p, with a and b under it, and c under a. */
const thread = (): readonly ThreadEntry[] =>
  insertReplies(insertReplies(threadOf(post('p')), 'p', [post('a'), post('b')]), 'a', [post('c')])

describe('thread entries', () => {
  it('starts with the post itself, at the margin', () => {
    expect(shape(threadOf(post('p')))).toBe('p0')
  })

  it('puts replies under the post they answer and opens it', () => {
    expect(shape(insertReplies(threadOf(post('p')), 'p', [post('a'), post('b')]))).toBe('p0* a1 b1')
  })

  it('says a post is closed when there was nothing under it', () => {
    expect(shape(insertReplies(threadOf(post('p')), 'p', []))).toBe('p0')
  })

  it('nests a level under a reply, not under the post', () => {
    expect(shape(thread())).toBe('p0* a1* c2 b1')
  })

  it('replaces the replies it already showed', () => {
    expect(shape(insertReplies(thread(), 'p', [post('x')]))).toBe('p0* x1')
  })

  it('stops indenting at the deepest level it draws', () => {
    let entries = threadOf(post('p'))
    let parent = 'p'
    for (const id of ['a', 'b', 'c', 'd', 'e']) {
      entries = insertReplies(entries, parent, [post(id)])
      parent = id
    }
    expect(shape(entries)).toBe('p0* a1* b2* c3* d3* e3')
  })

  it('takes the replies under a post off the screen again', () => {
    expect(shape(dropReplies(thread(), 'p'))).toBe('p0')
    expect(shape(dropReplies(thread(), 'a'))).toBe('p0* a1 b1')
  })

  it('adds a reply after the ones already shown under that post', () => {
    expect(shape(appendReply(thread(), 'p', post('n')))).toBe('p0* a1* c2 b1 n1')
    expect(shape(appendReply(thread(), 'a', post('n')))).toBe('p0* a1* c2 n2 b1')
    expect(shape(appendReply(threadOf(post('p')), 'p', post('n')))).toBe('p0* n1')
  })

  it('puts the post the server sent back where its placeholder was', () => {
    const sent = replacePost(appendReply(threadOf(post('p')), 'p', post('pending')), 'pending', post('real'))
    expect(shape(sent)).toBe('p0* real1')
    expect(sent[1]!.post.id).toBe('real')
  })

  it('takes a post out with everything said under it', () => {
    expect(shape(removeEntry(thread(), 'a'))).toBe('p0* b1')
    expect(shape(removeEntry(thread(), 'p'))).toBe('')
  })

  it('does nothing to a post that is not on screen', () => {
    expect(shape(insertReplies(thread(), 'gone', [post('x')]))).toBe('p0* a1* c2 b1')
    expect(shape(dropReplies(thread(), 'gone'))).toBe('p0* a1* c2 b1')
    expect(shape(appendReply(thread(), 'gone', post('x')))).toBe('p0* a1* c2 b1')
    expect(shape(removeEntry(thread(), 'gone'))).toBe('p0* a1* c2 b1')
  })
})
