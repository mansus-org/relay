import { StyleSheet, Text, View } from 'react-native'
import Svg, { Path } from 'react-native-svg'

import { timeAgo, type Post } from '../../domain'
import { colors, fonts, line } from '../theme'
import { Avatar } from './Avatar'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

type Props = { post: Post; placeName: string | null; now: Date }

function ChatIcon() {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path d="M4 4h16v12H9l-5 4z" fill="none" stroke={colors.ink} strokeWidth={2.2} strokeLinejoin="miter" />
    </Svg>
  )
}

/** Feed post: author, "time · place", body, then a footer with reactions and the reply count. */
export function PostCard({ post, placeName, now }: Props) {
  const when = [timeAgo(post.createdAt, now), placeName].filter(Boolean).join(' · ')
  const replies = post.replyCount
  return (
    <HardShadow>
      <View
        style={styles.card}
        accessible
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
        {post.reactions.length > 0 || replies > 0 ? (
          <View style={styles.foot}>
            <View style={styles.reactions}>
              {post.reactions.map((r) => (
                <View key={r.emoji} style={[styles.react, r.mine && styles.mine]}>
                  <Text style={styles.emoji}>{r.emoji}</Text>
                  <MonoLabel size={13} tracking={0.02} color={r.mine ? colors.onRed : colors.ink}>
                    {String(r.count)}
                  </MonoLabel>
                </View>
              ))}
            </View>
            {replies > 0 ? (
              <View style={styles.replies}>
                <ChatIcon />
                <MonoLabel size={13} tracking={0.02}>
                  {String(replies)}
                </MonoLabel>
              </View>
            ) : null}
          </View>
        ) : null}
      </View>
    </HardShadow>
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
  react: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 34, paddingHorizontal: 10, borderWidth: line.regular, borderColor: colors.ink, backgroundColor: colors.paper },
  mine: { backgroundColor: colors.red },
  emoji: { fontSize: 14 },
  replies: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 6, height: 44 },
})
