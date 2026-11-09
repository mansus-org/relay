import { StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line } from '../theme'

type Tone = 'ochre' | 'ink' | 'spent' | 'plain'

const TONES: Record<Tone, { readonly bg: string; readonly fg: string; readonly border: string; readonly struck?: boolean }> = {
  ochre: { bg: colors.ochre, fg: colors.ink, border: colors.ink },
  ink: { bg: colors.ink, fg: colors.paper, border: colors.ink },
  spent: { bg: colors.surface, fg: colors.redText, border: colors.redText, struck: true },
  plain: { bg: 'transparent', fg: colors.ink, border: colors.ink },
}

/** The small caps state box on the right of a row: `PENDING`, `USED`, `OFF`. */
export function Pill({ label, tone = 'plain' }: { label: string; tone?: Tone }) {
  const t = TONES[tone]
  return (
    <View style={[styles.pill, { backgroundColor: t.bg, borderColor: t.border }]}>
      <Text style={[styles.text, { color: t.fg, textDecorationLine: t.struck ? 'line-through' : 'none' }]}>
        {label.toUpperCase()}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  pill: { height: 26, paddingHorizontal: 9, justifyContent: 'center', borderWidth: line.regular, borderColor: colors.ink },
  text: { fontFamily: fonts.monoBold, fontSize: 11, letterSpacing: 1.3 },
})
