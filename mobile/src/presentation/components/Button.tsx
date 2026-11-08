import { useState } from 'react'
import { Pressable, StyleSheet } from 'react-native'

import { colors, line, minTap } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

type Props = {
  label: string
  onPress: () => void
  disabled?: boolean
  busy?: boolean
  /** 'sm' is the 44px header variant. */
  size?: 'md' | 'sm'
  /** 'ghost' is an underlined red text button with no box. */
  variant?: 'primary' | 'ghost'
}

/** Red block button with a hard ink shadow. Disabled turns paper2 with muted text and no shadow. */
export function Button({ label, onPress, disabled = false, busy = false, size = 'md', variant = 'primary' }: Props) {
  const [pressed, setPressed] = useState(false)
  const inactive = disabled || busy
  if (variant === 'ghost') {
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: inactive, busy }}
        disabled={inactive}
        onPress={onPress}
        style={styles.ghost}
      >
        <MonoLabel size={14} tracking={0.16} color={colors.redText} style={styles.ghostText}>
          {label}
        </MonoLabel>
      </Pressable>
    )
  }
  const face = (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy }}
      disabled={inactive}
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      style={[styles.button, size === 'sm' && styles.small, inactive ? styles.inactive : styles.active]}
    >
      <MonoLabel size={size === 'sm' ? 12.5 : 14} tracking={size === 'sm' ? 0.12 : 0.16} color={inactive ? colors.ink2 : colors.onRed}>
        {label}
      </MonoLabel>
    </Pressable>
  )
  if (inactive) return <HardShadow offset={0}>{face}</HardShadow>
  return (
    <HardShadow pressed={pressed} offset={size === 'sm' ? 3 : 5}>
      {face}
    </HardShadow>
  )
}

const styles = StyleSheet.create({
  button: { height: 50, minHeight: minTap, borderWidth: line.strong, alignItems: 'center', justifyContent: 'center' },
  small: { height: 44, paddingHorizontal: 16, borderWidth: line.regular },
  ghost: { height: 50, minHeight: minTap, alignItems: 'center', justifyContent: 'center' },
  ghostText: { textDecorationLine: 'underline' },
  active: { backgroundColor: colors.red, borderColor: colors.ink },
  inactive: { backgroundColor: colors.paper2, borderColor: colors.ink2 },
})
