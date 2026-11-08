import { Pressable, StyleSheet } from 'react-native'

import { colors, line, minTap } from '../theme'
import { MonoLabel } from './MonoLabel'

type Props = {
  label: string
  /** Trailing mark such as "✕" or "▾". */
  suffix?: string
  tone?: 'plain' | 'red' | 'on'
  onPress?: () => void
  accessibilityLabel?: string
  accessibilityState?: { selected?: boolean }
}

/** Mono pill, 34px visible with a 44px tap target. `red` flags location, `on` is the selected state. */
export function Chip({ label, suffix, tone = 'plain', onPress, accessibilityLabel, accessibilityState }: Props) {
  const color = tone === 'red' ? colors.redText : tone === 'on' ? colors.paper : colors.ink
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={accessibilityState}
      disabled={!onPress}
      onPress={onPress}
      hitSlop={5}
      style={[styles.chip, tone === 'red' && styles.red, tone === 'on' && styles.on, { minHeight: minTap - 10 }]}
    >
      <MonoLabel size={11.5} tracking={0.08} color={color}>
        {suffix ? `${label}  ${suffix}` : label}
      </MonoLabel>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  chip: {
    height: 34,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: line.regular,
    borderColor: colors.ink,
    backgroundColor: colors.surface,
  },
  red: { borderColor: colors.redText },
  on: { backgroundColor: colors.ink },
})
