import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { canRemoveMember, dayMonthYear, logEntryLabel, dateTime, type MemberDetail } from '../../domain'
import { colors, fonts, line } from '../theme'
import { Avatar } from './Avatar'
import { Button } from './Button'
import { GeoRing, GeoSun } from './Geo'
import { MonoLabel } from './MonoLabel'
import { Pill } from './Pill'

type Props = {
  /** Null closes the sheet. */
  detail: MemberDetail | null
  /** Your own handle: the node will not let you switch off your own account, or anybody else's. */
  myHandle: string
  removing: boolean
  onClose: () => void
  onRemove: () => void
}

/**
 * One account, and everything moderation already did to it.
 *
 * The node has no count of a member's posts to hand over, so the second box counts what it does
 * know: how many lines of the trail carry this account's name. Zero is the ordinary answer and
 * it is said as plainly as any other.
 */
export function MemberSheet({ detail, myHandle, removing, onClose, onRemove }: Props) {
  const { bottom } = useSafeAreaInsets()
  const member = detail?.member ?? null
  const history = detail?.history ?? []
  const removable = member !== null && canRemoveMember(member, myHandle)
  return (
    <Modal visible={member !== null} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.root}>
        <Pressable accessibilityLabel="Close" accessibilityRole="button" style={styles.scrim} onPress={onClose} />
        <View style={[styles.sheet, { paddingBottom: bottom + 20 }]}>
          <View style={styles.grab} />
          {member === null ? null : (
            <>
              <View style={styles.id}>
                <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                  <GeoRing size={110} right={-24} top={-30} color={colors.paper} />
                  <GeoSun size={60} right={18} top={26} color={colors.ochre} />
                </View>
                <Avatar name={member.name} seed={member.handle} size={56} />
                <View style={styles.idMain}>
                  <Text style={styles.idName} numberOfLines={1}>
                    {member.name}
                  </Text>
                  <Text style={styles.idHandle}>@{member.handle}</Text>
                </View>
                {member.deactivatedAt === null ? null : <Pill label="Off" tone="ochre" />}
              </View>
              <View style={styles.stats}>
                <View style={[styles.stat, styles.statWide]}>
                  <MonoLabel size={11} tracking={1.6} color={colors.ink2}>
                    JOINED
                  </MonoLabel>
                  <Text style={styles.statValue}>{dayMonthYear(member.joinedAt).toUpperCase()}</Text>
                </View>
                <View style={[styles.stat, styles.statNext]}>
                  <MonoLabel size={11} tracking={1.6} color={colors.ink2}>
                    IN THE RECORD
                  </MonoLabel>
                  <Text style={styles.statValue}>{history.length === 0 ? 'NOTHING' : String(history.length)}</Text>
                </View>
              </View>
              {history.length === 0 ? null : (
                <ScrollView style={styles.log} accessibilityLabel="What moderation did to this account">
                  {history.map((entry) => (
                    <View key={entry.id} style={styles.logRow}>
                      <View style={styles.logMain}>
                        <Text style={styles.logLabel}>{logEntryLabel(entry)}</Text>
                      </View>
                      <Text style={styles.logWhen}>{dateTime(entry.createdAt).toUpperCase()}</Text>
                    </View>
                  ))}
                </ScrollView>
              )}
              {removable ? (
                <View style={styles.actions}>
                  <Button label="Remove member" busy={removing} onPress={onRemove} />
                  <Button label="Close" variant="outline" onPress={onClose} />
                </View>
              ) : (
                <View style={styles.actions}>
                  <Text style={styles.note}>
                    {member.deactivatedAt !== null
                      ? 'This account is already switched off.'
                      : 'Admins cannot be switched off from here.'}
                  </Text>
                  <Button label="Close" variant="outline" onPress={onClose} />
                </View>
              )}
            </>
          )}
        </View>
      </View>
    </Modal>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  scrim: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(20,18,16,.55)' },
  sheet: { backgroundColor: colors.surface, borderTopWidth: line.strong, borderColor: colors.ink, paddingHorizontal: 20, paddingTop: 10 },
  grab: { width: 48, height: 6, backgroundColor: colors.ink, alignSelf: 'center', marginBottom: 16 },
  id: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderWidth: line.regular,
    borderColor: colors.ink,
    backgroundColor: colors.ink,
    padding: 14,
    marginTop: 6,
    marginBottom: 16,
    overflow: 'hidden',
  },
  idMain: { flex: 1, gap: 4 },
  idName: { fontFamily: fonts.display, fontSize: 32, lineHeight: 32, textTransform: 'uppercase', color: colors.paper },
  idHandle: { fontFamily: fonts.mono, fontSize: 12, letterSpacing: 1.2, color: colors.ochre },
  stats: { flexDirection: 'row', borderWidth: line.regular, borderColor: colors.ink, backgroundColor: colors.paper },
  stat: { flex: 1, paddingVertical: 12, paddingHorizontal: 14 },
  statWide: { flexGrow: 1.5 },
  statNext: { borderLeftWidth: line.regular, borderLeftColor: colors.ink },
  statValue: { fontFamily: fonts.display, fontSize: 24, lineHeight: 27, textTransform: 'uppercase', color: colors.ink, marginTop: 2 },
  log: { flexGrow: 0, maxHeight: 220, marginTop: 16 },
  logRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 9,
    borderTopWidth: 1.5,
    borderTopColor: colors.ink,
  },
  logMain: { flex: 1 },
  logLabel: { fontFamily: fonts.body, fontSize: 14, lineHeight: 19, color: colors.ink },
  logWhen: { fontFamily: fonts.mono, fontSize: 10.5, letterSpacing: 0.6, color: colors.ink2 },
  actions: { gap: 12, marginTop: 18 },
  note: { fontFamily: fonts.body, fontSize: 14, lineHeight: 20, color: colors.ink2 },
})
