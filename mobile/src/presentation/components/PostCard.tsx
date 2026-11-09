import { Pressable, StyleSheet, Text, View } from 'react-native'
import Svg, { Path } from 'react-native-svg'

import { timeAgo, type Post } from '../../domain'
import { colors, fonts, line } from '../theme'
import { Avatar } from './Avatar'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'
import { ReactionRow } from './ReactionRow'

type Props = {
  post: Post
  placeName: string | null
  now: Date
  /** Opens the thread this post started. Without it the card is not pressable. */
  onPress?: () => void
  /** Taps one of this post's reactions on, or takes the reader's own back off. */
  onToggleReaction: (emoji: string) => void
}

function ChatIcon() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path d="M4 4h16v12H9l-5 4z" fill="none" stroke={colors.ink} strokeWidth={2.2} strokeLinejoin="miter" />
    </Svg>
  )
}

/** Feed post: author, "time · place", body, then a footer with reactions and the reply count. */
export function PostCard({ post, placeName, now, onPress, onToggleReaction }: Props) {
  const when = [timeAgo(post.createdAt, now), placeName].filter(Boolean).join(' · ')
  const replies = post.replyCount
  const card = (
    <HardShadow>
      <View
        style={styles.card}
        accessible
        accessibilityRole={onPress ? 'button' : undefined}
        accessibilityLabel={`${post.author.name}, ${when}. ${post.body}. ${replies} ${replies === 1 ? 'reply' : 'replies'}`}
      >
        <View style={styles.head}>
          <Avatar name={post.author.name} seed={post.author.id} />
          <View style={styles.who}>
            <Text style={styles.name} numberOfLines={1}>
              {post.author.name}
            </Text>
            <MonoLabel size={11} tracking={0.08} color={colors.ink2} style={styles.when} numberOfLines={1}>
              {when}
            </MonoLabel>
          </View>
        </View>
        <Text style={styles.body}>{post.body}</Text>
        <View style={styles.foot}>
          <ReactionRow onToggle={onToggleReaction} reactions={post.reactions} style={styles.reactions} />
          {replies > 0 ? (
            <View style={styles.replies}>
              <ChatIcon />
              <MonoLabel size={13} tracking={0.02}>
                {String(replies)}
              </MonoLabel>
            </View>
          ) : null}
        </View>
      </View>
    </HardShadow>
  )
  return onPress ? (
    <Pressable accessibilityRole="button" onPress={onPress}>
      {card}
    </Pressable>
  ) : (
    card
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink, paddingTop: 14, paddingHorizontal: 16 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  who: { flex: 1 },
  name: { fontFamily: fonts.bodyMedium, fontSize: 18, color: colors.ink },
  when: { marginTop: 3 },
  body: { marginTop: 12, paddingBottom: 14, fontFamily: fonts.body, fontSize: 17.5, lineHeight: 25, color: colors.ink },
  foot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: -16,
    paddingHorizontal: 16,
    minHeight: 54,
    borderTopWidth: line.regular,
    borderTopColor: colors.ink,
  },
  reactions: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 },
  replies: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 6, height: 44 },
})
