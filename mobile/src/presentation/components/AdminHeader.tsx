import type { ReactNode } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, fonts, minTap } from '../theme'
import { MonoLabel } from './MonoLabel'
import { Segmented, type SegmentOption } from './Segmented'

export type AdminTab = 'queue' | 'members' | 'invites'

export const ADMIN_TABS: readonly SegmentOption<AdminTab>[] = [
  { value: 'queue', label: 'Queue' },
  { value: 'members', label: 'Members' },
  { value: 'invites', label: 'Invites' },
]

type Props = {
  /** The line under the title, e.g. `Review queue · 5 posts`. */
  sub: string
  tab: AdminTab
  onTab: (tab: AdminTab) => void
  onBack: () => void
  /** Geometric shapes bleeding off the right edge of the band. */
  decoration?: ReactNode
}

/** The band every moderation screen wears: back to Settings, the title, and the three sections. */
export function AdminHeader({ sub, tab, onTab, onBack, decoration }: Props) {
  const { top } = useSafeAreaInsets()
  return (
    <View>
      <View style={[styles.band, { paddingTop: top + 8 }]}>
        <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {decoration}
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Back to Settings" onPress={onBack} style={styles.back}>
          <MonoLabel size={12} tracking={0.14} color={colors.ochre}>
            ‹ Settings
          </MonoLabel>
        </Pressable>
        <Text accessibilityRole="header" style={styles.title}>
          Mod<Text style={styles.ochre}>eration</Text>
        </Text>
        {sub ? (
          <MonoLabel size={11} tracking={0.14} color={colors.ochre} style={styles.sub}>
            {sub}
          </MonoLabel>
        ) : null}
      </View>
      <View style={styles.seg}>
        <Segmented label="Moderation section" options={ADMIN_TABS} value={tab} onChange={onTab} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  band: {
    backgroundColor: colors.ink,
    borderBottomWidth: 6,
    borderBottomColor: colors.red,
    paddingHorizontal: 16,
    paddingBottom: 16,
    overflow: 'hidden',
  },
  back: { alignSelf: 'flex-start', minHeight: minTap, justifyContent: 'center', marginLeft: -6, paddingRight: 6 },
  title: { marginTop: 2, fontFamily: fonts.display, fontSize: 50, lineHeight: 45, color: colors.paper, textTransform: 'uppercase' },
  ochre: { color: colors.ochre },
  sub: { marginTop: 6 },
  seg: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 4 },
})
