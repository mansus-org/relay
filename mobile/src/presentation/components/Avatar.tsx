import { StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line } from '../theme'

const palette = [
  { bg: colors.red, fg: colors.onRed },
  { bg: colors.ink, fg: colors.paper },
  { bg: colors.ochre, fg: colors.ink },
  { bg: '#25457a', fg: colors.paper },
  { bg: '#3c5a33', fg: colors.paper },
  { bg: '#6e2f5f', fg: colors.paper },
]

const slotOf = (seed: string) => [...seed].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % palette.length

/** Square initial; the colour is derived from `seed` so a person keeps theirs. */
export function Avatar({ name, seed = name, size = 42 }: { name: string; seed?: string; size?: number }) {
  const { bg, fg } = palette[slotOf(seed)]!
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.box, { width: size, height: size, backgroundColor: bg }]}
    >
      <Text style={[styles.initial, { color: fg, fontSize: size * 0.48, lineHeight: size * 0.6 }]}>{name.trim().charAt(0).toUpperCase() || '?'}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  box: { alignItems: 'center', justifyContent: 'center', borderWidth: line.regular, borderColor: colors.ink },
  initial: { fontFamily: fonts.display },
})
