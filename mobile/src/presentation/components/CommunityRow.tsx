import { Pressable, StyleSheet, Text, View } from 'react-native'

import { excerpt, formatDistance, type NearbyCommunity } from '../../domain'
import { colors, fonts, line, minTap } from '../theme'
import { Avatar } from './Avatar'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

type Props = { community: NearbyCommunity; onPress: () => void }

/** A community in the nearby list. Joined gets a red tag, out of range turns dashed and grey. */
export function CommunityRow({ community, onPress }: Props) {
  const { name, description, memberCount, isMember, inRange } = community
  const distance = formatDistance(community.distanceKm)
  const off = !inRange && !isMember
  const status = isMember ? 'Joined' : off ? 'Out of range' : null
  const label = [name, excerpt(description, 120), `${memberCount} members`, distance, status].filter(Boolean).join('. ')
  return (
    <View style={styles.wrap}>
      <HardShadow color={isMember ? colors.red : colors.ink} offset={off ? 0 : 5}>
        <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={[styles.card, off && styles.off]}>
          <Avatar name={name} seed={community.id} size={52} />
          <View style={styles.main}>
            <Text style={[styles.title, off && { color: colors.ink2 }]} numberOfLines={2}>
              {name.toUpperCase()}
            </Text>
            {description ? (
              <Text style={styles.excerpt} numberOfLines={2}>
                {excerpt(description, 120)}
              </Text>
            ) : null}
            <View style={[styles.meta, off && { borderTopColor: colors.ink2 }]}>
              <MonoLabel size={11} tracking={0.1} color={off ? colors.ink2 : colors.ink}>
                {`${memberCount} members`}
              </MonoLabel>
              {distance ? (
                <MonoLabel size={11} tracking={0.1} color={off ? colors.ink2 : colors.ink}>
                  {distance}
                </MonoLabel>
              ) : null}
            </View>
          </View>
        </Pressable>
      </HardShadow>
      {status ? (
        <View pointerEvents="none" style={[styles.tag, isMember ? styles.joined : styles.outOfRange]}>
          <MonoLabel size={10.5} tracking={0.12} color={isMember ? colors.onRed : colors.ink}>
            {status}
          </MonoLabel>
        </View>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { position: 'relative' },
  card: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', minHeight: minTap, padding: 14, backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink },
  off: { backgroundColor: colors.paper2, borderStyle: 'dashed', borderColor: colors.ink2 },
  main: { flex: 1 },
  title: { fontFamily: fonts.display, fontSize: 22, lineHeight: 24, color: colors.ink },
  excerpt: { marginTop: 6, fontFamily: fonts.body, fontSize: 16, lineHeight: 21, color: colors.ink2 },
  meta: { flexDirection: 'row', gap: 14, marginTop: 8, paddingTop: 8, borderTopWidth: 1.5, borderTopColor: colors.ink },
  tag: { position: 'absolute', top: -12, right: 10, height: 26, paddingHorizontal: 9, justifyContent: 'center', transform: [{ rotate: '3deg' }], borderWidth: line.regular },
  joined: { backgroundColor: colors.red, borderColor: colors.ink },
  outOfRange: { backgroundColor: colors.paper, borderColor: colors.ink, borderStyle: 'dashed' },
})
