import { Pressable, StyleSheet, Text, View } from 'react-native'

import { dayMonthYear, type AdminMember } from '../../domain'
import { colors, fonts, minTap } from '../theme'
import { Avatar } from './Avatar'
import { Pill } from './Pill'

type Props = {
  member: AdminMember
  /** The first row in the box wears no rule above itself. */
  first?: boolean
  onPress: () => void
}

/**
 * One account on the node.
 *
 * Nobody is deleted here, so an account that has been switched off keeps its row and keeps its
 * name in every trail; the only difference is the box where the joining date was.
 */
export function MemberRow({ member, first = false, onPress }: Props) {
  const off = member.deactivatedAt !== null
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${member.name}, @${member.handle}${off ? ', switched off' : ''}`}
      onPress={onPress}
      style={({ pressed }) => [styles.row, first && styles.first, pressed && styles.pressed]}
    >
      <Avatar name={member.name} seed={member.handle} size={42} />
      <View style={styles.main}>
        <Text style={styles.title} numberOfLines={1}>
          {member.name}
        </Text>
        <Text style={styles.sub} numberOfLines={1}>
          @{member.handle}
        </Text>
      </View>
      {off ? <Pill label="Off" tone="ink" /> : <Text style={styles.end}>{dayMonthYear(member.joinedAt).toUpperCase()}</Text>}
    </Pressable>
  )
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: Math.max(58, minTap),
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: colors.surface,
    borderTopWidth: 1.5,
    borderTopColor: colors.ink,
  },
  first: { borderTopWidth: 0 },
  pressed: { backgroundColor: colors.paper2 },
  main: { flex: 1, gap: 2 },
  title: { fontFamily: fonts.bodyMedium, fontSize: 17, lineHeight: 21, color: colors.ink },
  sub: { fontFamily: fonts.body, fontSize: 14, color: colors.ink2 },
  end: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 0.9, color: colors.ink2 },
})
