import { StyleSheet, Text, View } from 'react-native'

import { aiBadge, type AiDecision } from '../../domain'
import { colors, fonts, line, shadow } from '../theme'

const TONES: Record<'ok' | 'warn' | 'bad', { readonly bg: string; readonly fg: string }> = {
  ok: { bg: colors.surface, fg: colors.ink },
  warn: { bg: colors.ochre, fg: colors.ink },
  bad: { bg: colors.red, fg: colors.onRed },
}

/**
 * What a model made of a post, as a square chip: `FLAGGED 82%`.
 *
 * It renders nothing when no model has looked. That is different from one that looked and
 * found nothing, and a chip that lied about the difference would be worse than no chip.
 */
export function AiBadge({ ai, large = false }: { ai: AiDecision | null; large?: boolean }) {
  const badge = aiBadge(ai)
  if (!badge) return null
  const tone = TONES[badge.tone]
  return (
    <View
      accessibilityLabel={`Model review: ${badge.label}`}
      style={[styles.badge, large && styles.large, { backgroundColor: tone.bg }]}
    >
      <Text style={[styles.text, large && styles.largeText, { color: tone.fg }]}>{badge.label.toUpperCase()}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderWidth: line.regular,
    borderColor: colors.ink,
  },
  large: { paddingHorizontal: 12, paddingVertical: 5, shadowColor: colors.ink, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: shadow.small, height: shadow.small } },
  text: { fontFamily: fonts.monoBold, fontSize: 11, letterSpacing: 1.4 },
  largeText: { fontSize: 13, letterSpacing: 1.6 },
})
