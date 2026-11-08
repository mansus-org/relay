import type { ReactNode } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, fonts, minTap } from '../theme'
import { MonoLabel } from './MonoLabel'

type Props = {
  title: string
  subtitle?: string
  cancelLabel?: string
  onCancel: () => void
  /** Right end of the action row, e.g. a small Button. */
  action?: ReactNode
  decoration?: ReactNode
}

/** Large black navigation band for pushed screens: Cancel left, action right, display title below. */
export function NavBar({ title, subtitle, cancelLabel = 'Cancel', onCancel, action, decoration }: Props) {
  const { top } = useSafeAreaInsets()
  return (
    <View style={[styles.band, { paddingTop: top + 8 }]}>
      <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        {decoration}
      </View>
      <View style={styles.row}>
        <Pressable accessibilityRole="button" accessibilityLabel={cancelLabel} onPress={onCancel} style={styles.cancel}>
          <MonoLabel size={13} tracking={0.12} color={colors.paper}>
            {cancelLabel}
          </MonoLabel>
        </Pressable>
        {action}
      </View>
      <Text accessibilityRole="header" style={styles.title}>
        {title.toUpperCase()}
      </Text>
      {subtitle ? (
        <MonoLabel size={11} tracking={0.14} color={colors.ochre} style={styles.sub}>
          {subtitle}
        </MonoLabel>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  band: { backgroundColor: colors.ink, borderBottomWidth: 6, borderBottomColor: colors.red, paddingHorizontal: 16, paddingBottom: 14, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  cancel: { minWidth: minTap, height: minTap, justifyContent: 'center', marginLeft: -6, paddingHorizontal: 6 },
  title: { marginTop: 4, fontFamily: fonts.display, fontSize: 38, lineHeight: 40, color: colors.paper },
  sub: { marginTop: 6 },
})
