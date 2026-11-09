import { StyleSheet, Text, View } from 'react-native'

import { describeNodeTest, type NodeTest } from '../../domain'
import { colors, fonts, line } from '../theme'
import { HardShadow } from './HardShadow'
import { CheckIcon, WarnIcon } from './icons'

/**
 * What one test of a node found, in one block: ochre-flagged ink when it answered, ink-flagged red
 * when it did not. The sentence comes from the domain, so the row and this can never disagree.
 */
export function NodeTestResult({ test }: { test: NodeTest }) {
  const ok = test.reachable
  return (
    <HardShadow color={ok ? colors.ochre : colors.ink} style={styles.wrap}>
      <View style={[styles.box, ok ? styles.ok : styles.err]} accessibilityRole="alert" accessibilityLiveRegion="polite">
        <View style={[styles.flag, ok ? styles.flagOk : styles.flagErr]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {ok ? <CheckIcon size={28} color={colors.ink} /> : <WarnIcon size={28} color={colors.ochre} />}
        </View>
        <Text style={[styles.text, ok ? styles.textOk : styles.textErr]}>{describeNodeTest(test)}</Text>
      </View>
    </HardShadow>
  )
}

const styles = StyleSheet.create({
  wrap: { marginTop: 18 },
  box: { flexDirection: 'row', alignItems: 'stretch', borderWidth: line.strong, borderColor: colors.ink },
  ok: { backgroundColor: colors.ink },
  err: { backgroundColor: colors.red },
  flag: { width: 50, alignItems: 'center', justifyContent: 'center' },
  flagOk: { backgroundColor: colors.ochre },
  flagErr: { backgroundColor: colors.ink },
  text: { flex: 1, paddingHorizontal: 14, paddingVertical: 12, fontFamily: fonts.bodyMedium, fontSize: 16, lineHeight: 21 },
  textOk: { color: colors.paper },
  textErr: { color: colors.onRed },
})
