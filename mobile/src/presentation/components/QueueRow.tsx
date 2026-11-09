import { Pressable, StyleSheet, Text, View } from 'react-native'

import { aiVerdict, authorLabel, timeAgo, type ModeratedPost } from '../../domain'
import { colors, fonts, line, shadow } from '../theme'
import { AiBadge } from './AiBadge'
import { Avatar } from './Avatar'
import { HardShadow } from './HardShadow'

const BAR = { flagged: colors.ochre, removed: colors.red } as const

type Props = {
  post: ModeratedPost
  onPress: () => void
}

/**
 * One post waiting for a decision.
 *
 * The bar down its left side is the model's opinion, not the post's fate: ochre when it wants a
 * human, red when it wants the post gone, ink when nothing has said anything yet. The name is
 * only as good as an id can be, because the queue carries an `author_id` and the node does not
 * join it to an account.
 */
export function QueueRow({ post, onPress }: Props) {
  const verdict = aiVerdict(post.ai)
  const bar = verdict ? BAR[verdict as 'flagged' | 'removed'] : undefined
  return (
    <HardShadow offset={shadow.small}>
      <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
        <View style={[styles.bar, bar ? { backgroundColor: bar } : null]} />
        <View style={styles.top}>
          <Avatar name={post.authorId} seed={post.authorId} size={30} />
          <View style={styles.who}>
            <Text style={styles.name} numberOfLines={1}>
              {authorLabel(post.authorId)}
            </Text>
            <Text style={styles.when}>{timeAgo(post.createdAt, new Date()).toUpperCase()}</Text>
          </View>
          <AiBadge ai={post.ai} />
        </View>
        <Text style={styles.body} numberOfLines={2}>
          {post.body}
        </Text>
      </Pressable>
    </HardShadow>
  )
}

const styles = StyleSheet.create({
  row: {
    position: 'relative',
    backgroundColor: colors.surface,
    borderWidth: line.regular,
    borderColor: colors.ink,
    paddingTop: 12,
    paddingHorizontal: 14,
    paddingBottom: 14,
    paddingLeft: 22,
    overflow: 'hidden',
  },
  pressed: { backgroundColor: colors.paper2 },
  bar: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 8, backgroundColor: colors.ink, borderRightWidth: line.regular, borderRightColor: colors.ink },
  top: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  who: { flex: 1, gap: 3 },
  name: { fontFamily: fonts.bodyMedium, fontSize: 18, color: colors.ink },
  when: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 0.9, color: colors.ink2 },
  body: { marginTop: 8, fontFamily: fonts.body, fontSize: 17, lineHeight: 24, color: colors.ink },
})
