import { useState } from 'react'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'

import { timeAgo, type ThreadEntry } from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { Avatar } from '../../../src/presentation/components/Avatar'
import { Button } from '../../../src/presentation/components/Button'
import { FeedPostCard } from '../../../src/presentation/components/FeedPostCard'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../src/presentation/components/NavBar'
import { ReactionRow } from '../../../src/presentation/components/ReactionRow'
import { colors, fonts, line, minTap } from '../../../src/presentation/theme'
import { useThread } from '../../../src/presentation/use-post'

/** How far a reply sits from the post it answers, in the thread's own indentation. */
const indent = (depth: number) => ({
  marginLeft: (depth - 1) * 14,
  paddingLeft: depth > 1 ? 14 : 0,
  borderLeftWidth: depth > 1 ? 3 : 0,
  borderLeftColor: depth > 2 ? colors.red : colors.ink,
})

type ReplyProps = {
  entry: ThreadEntry
  now: Date
  /** True while this reply's own answers are on their way. */
  loading: boolean
  onReact: (emoji: string) => void
  onReplyTo: () => void
  onToggleReplies: () => void
}

/** One thing someone said, with the answers it is holding and the ways to answer it back. */
function Reply({ entry, now, loading, onReact, onReplyTo, onToggleReplies }: ReplyProps) {
  const { post, depth, open } = entry
  const label = loading ? 'Loading replies' : open ? 'Hide replies' : `Show ${post.replyCount} ${post.replyCount === 1 ? 'reply' : 'replies'}`
  return (
    <View style={[styles.reply, indent(depth)]}>
      <Avatar name={post.author.name} seed={post.author.id} size={30} />
      <View style={styles.replyBody}>
        <View style={styles.who}>
          <Text style={styles.name}>{post.author.name}</Text>
          <MonoLabel size={11} tracking={0.08} color={colors.ink2}>
            {timeAgo(post.createdAt, now)}
          </MonoLabel>
        </View>
        <Text style={styles.replyText}>{post.body}</Text>
        <ReactionRow onToggle={onReact} reactions={post.reactions} style={styles.replyReactions} />
        <View style={styles.links}>
          <Pressable accessibilityLabel={`Reply to ${post.author.name}`} accessibilityRole="button" hitSlop={8} onPress={onReplyTo}>
            <MonoLabel color={colors.redText} size={11} tracking={0.14}>
              REPLY
            </MonoLabel>
          </Pressable>
          {post.replyCount > 0 ? (
            <Pressable
              accessibilityLabel={label}
              accessibilityRole="button"
              hitSlop={8}
              onPress={onToggleReplies}
              style={styles.more}
            >
              <View style={styles.moreBox}>
                <Text style={styles.moreMark}>{open ? '−' : '+'}</Text>
              </View>
              <MonoLabel color={colors.redText} size={11} tracking={0.14}>
                {label}
              </MonoLabel>
            </Pressable>
          ) : null}
        </View>
      </View>
    </View>
  )
}

export default function Thread() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const router = useRouter()
  const { state, toggleReplies, toggleReaction, askReplyTo, sendReply, clearProblem } = useThread(id)
  const [now] = useState(() => new Date())
  const [body, setBody] = useState('')

  const back = () => router.back()
  const root = state.entries[0] ?? null
  const target = state.replyingTo ?? root
  const send = async () => {
    if (await sendReply(body)) setBody('')
  }

  if (!state.loaded) {
    return (
      <View style={styles.screen}>
        <NavBar title="Thread" cancelLabel="‹ Back" onCancel={back} />
        <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading thread" />
      </View>
    )
  }

  if (state.failed || !root) {
    return (
      <View style={styles.screen}>
        <NavBar title="Thread" cancelLabel="‹ Back" onCancel={back} />
        <View style={styles.pad}>
          <Alert message="That post is not here any more." />
        </View>
      </View>
    )
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.screen}>
      <NavBar
        title="Thread"
        cancelLabel="‹ Back"
        onCancel={back}
        action={
          root.post.replyCount > 0 ? (
            <View style={styles.stamp}>
              <MonoLabel size={11} tracking={0.14}>
                {`${root.post.replyCount} ${root.post.replyCount === 1 ? 'reply' : 'replies'}`}
              </MonoLabel>
            </View>
          ) : null
        }
      />
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.pad}>
          <FeedPostCard now={now} post={root.post} onToggleReaction={(emoji) => void toggleReaction(root.post, emoji)} />
          {state.problem ? <Alert message={state.problem} /> : null}
        </View>
        <View style={styles.section}>
          <View style={styles.sectionRule} />
          <MonoLabel size={11} tracking={0.18}>
            REPLIES
          </MonoLabel>
        </View>
        <View style={styles.pad}>
          {state.entries.length === 1 && root.post.replyCount === 0 ? (
            <Text style={styles.none}>Nothing has answered this post yet.</Text>
          ) : null}
          {state.entries.slice(1).map((entry) => (
            <Reply
              entry={entry}
              key={entry.post.id}
              loading={state.loadingRepliesFor === entry.post.id}
              now={now}
              onReact={(emoji) => void toggleReaction(entry.post, emoji)}
              onReplyTo={() => askReplyTo(entry.post.id)}
              onToggleReplies={() => void toggleReplies(entry.post)}
            />
          ))}
        </View>
      </ScrollView>
      <View style={styles.bar}>
        <TextInput
          accessibilityLabel={`Reply to ${target?.post.author.name ?? 'this post'}`}
          multiline
          onChangeText={(text) => {
            setBody(text)
            if (state.problem) clearProblem()
          }}
          placeholder={`Reply to ${target?.post.author.name ?? 'this post'}`}
          placeholderTextColor={colors.ink2}
          style={styles.input}
          value={body}
        />
        <Button disabled={body.trim().length === 0} label="Send" onPress={() => void send()} size="sm" />
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  pad: { paddingHorizontal: 16 },
  scroll: { paddingBottom: 24 },
  status: { marginTop: 32 },
  stamp: { backgroundColor: colors.red, borderColor: colors.ink, borderWidth: line.regular, paddingHorizontal: 10, transform: [{ rotate: '-4deg' }] },
  section: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 22, paddingBottom: 10, paddingHorizontal: 20 },
  sectionRule: { width: 22, height: 3, backgroundColor: colors.red },
  none: { paddingTop: 4, fontFamily: fonts.body, fontSize: 17, color: colors.ink2 },
  reply: { flexDirection: 'row', gap: 10, paddingTop: 14 },
  replyBody: { flex: 1 },
  who: { flexDirection: 'row', alignItems: 'baseline', gap: 10 },
  name: { fontFamily: fonts.bodyMedium, fontSize: 16, color: colors.ink },
  replyText: { marginTop: 3, fontFamily: fonts.body, fontSize: 17, lineHeight: 24, color: colors.ink },
  replyReactions: { marginTop: 8 },
  links: { flexDirection: 'row', alignItems: 'center', gap: 16, minHeight: minTap },
  more: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  moreBox: { width: 20, height: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.red },
  moreMark: { color: colors.onRed, fontFamily: fonts.monoBold, fontSize: 14, lineHeight: 16 },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 10,
    paddingBottom: Platform.OS === 'ios' ? 26 : 10,
    backgroundColor: colors.paper,
    borderTopWidth: line.strong,
    borderTopColor: colors.ink,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: line.regular,
    borderColor: colors.ink,
    backgroundColor: colors.surface,
    fontFamily: fonts.body,
    fontSize: 17,
    lineHeight: 24,
    color: colors.ink,
  },
})
