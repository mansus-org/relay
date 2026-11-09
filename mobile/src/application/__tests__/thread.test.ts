import { err, ok, type Reaction } from '../../domain'
import { makeFakePostRepository, makePost } from '../../testing/fakes'
import { makeLoadReplies, makeLoadThread, makeReply } from '../thread'
import { makeToggleReaction } from '../react'

const tally = (emoji: string, count: number, mine = false): Reaction => ({ emoji, count, mine })

describe('load thread', () => {
  it('asks for the post by id', async () => {
    const { repository, calls } = makeFakePostRepository({ get: ok(makePost('p')) })
    expect(await makeLoadThread({ postRepository: repository })('p')).toEqual(ok(makePost('p')))
    expect(calls.get).toEqual(['p'])
  })

  it('says the post is gone when the server cannot find it', async () => {
    const { repository } = makeFakePostRepository({ get: err('network') })
    expect(await makeLoadThread({ postRepository: repository })('p')).toEqual(err('network'))
  })
})

describe('load replies', () => {
  it('reads one level, in the order the server gave', async () => {
    const { repository, calls } = makeFakePostRepository({ replies: ok([makePost('a'), makePost('b')]) })
    const result = await makeLoadReplies({ postRepository: repository })('p')
    expect(result.ok && result.value.map((p) => p.id)).toEqual(['a', 'b'])
    expect(calls.replies).toEqual(['p'])
  })
})

describe('reply', () => {
  it('sends the trimmed body and the post it answers', async () => {
    const { repository, calls } = makeFakePostRepository({ create: ok(makePost('r', { parentId: 'p' })) })
    const result = await makeReply({ postRepository: repository })({ parentId: 'p', body: '  nice  ' })
    expect(result.ok && result.value.id).toBe('r')
    expect(calls.create).toEqual([{ body: 'nice', parentId: 'p' }])
  })

  it.each([
    ['   ', 'empty'],
    ['x'.repeat(501), 'too-long'],
  ])('refuses %j without asking the server', async (body, expected) => {
    const { repository, calls } = makeFakePostRepository({ create: ok(makePost('r')) })
    expect(await makeReply({ postRepository: repository })({ parentId: 'p', body })).toEqual(err(expected))
    expect(calls.create).toEqual([])
  })

  it('passes the error through when the server refuses', async () => {
    const { repository } = makeFakePostRepository({ create: err('network') })
    expect(await makeReply({ postRepository: repository })({ parentId: 'p', body: 'hi' })).toEqual(err('network'))
  })
})

describe('toggle reaction', () => {
  const post = makePost('p', { reactions: [tally('👍', 2)] })

  it('leaves an emoji you have not left and keeps what the server counted', async () => {
    const { repository, calls } = makeFakePostRepository({ react: ok(tally('👍', 3, true)) })
    expect(await makeToggleReaction({ postRepository: repository })(post, '👍')).toEqual(ok(tally('👍', 3, true)))
    expect(calls.react).toEqual([{ postId: 'p', emoji: '👍' }])
    expect(calls.unreact).toEqual([])
  })

  it('takes back one you left, and answers zero because the server says nothing else', async () => {
    const { repository, calls } = makeFakePostRepository({ unreact: ok(undefined) })
    const left = makePost('p', { reactions: [tally('👍', 1, true)] })
    expect(await makeToggleReaction({ postRepository: repository })(left, '👍')).toEqual(ok(tally('👍', 0, false)))
    expect(calls.unreact).toEqual([{ postId: 'p', emoji: '👍' }])
    expect(calls.react).toEqual([])
  })

  it('reports the error and leaves the post as it was', async () => {
    const { repository } = makeFakePostRepository({ react: err('network') })
    expect(await makeToggleReaction({ postRepository: repository })(post, '🔥')).toEqual(err('network'))
  })
})
