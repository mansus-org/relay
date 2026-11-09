import { StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line, shadow } from '../theme'

type Tone = 'ochre' | 'ink' | 'red'

const TONES: Record<Tone, { readonly bg: string; readonly fg: string }> = {
  ochre: { bg: colors.ochre, fg: colors.ink },
  ink: { bg: colors.ink, fg: colors.paper },
  red: { bg: colors.red, fg: colors.onRed },
}

/** The rotated sticker that names a card: `FLAGGED`, `FRESH`, `CAN'T BE UNDONE`. */
export function Stamp({ label, tone = 'ochre' }: { label: string; tone?: Tone }) {
  const { bg, fg } = TONES[tone]
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.stamp, { backgroundColor: bg }]}
    >
      <Text style={[styles.text, { color: fg }]}>{label.toUpperCase()}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  stamp: {
    alignSelf: 'flex-start',
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderWidth: line.regular,
    borderColor: colors.ink,
    transform: [{ rotate: '-3deg' }],
    shadowColor: colors.ink,
    shadowOpacity: 1,
    shadowRadius: 0,
    shadowOffset: { width: shadow.small, height: shadow.small },
  },
  text: { fontFamily: fonts.monoBold, fontSize: 11, letterSpacing: 1.8 },
})
