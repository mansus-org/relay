import { Pressable, StyleSheet, Text, View } from 'react-native'

import { colors, fonts, minTap } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

/** Tilted ink pill with a red arrow flag; tapping it shows the buffered posts. */
export function NewPostsBanner({ count, onPress }: { count: number; onPress: () => void }) {
  const label = count === 1 ? '1 new post' : `${count} new posts`
  return (
    <View pointerEvents="box-none" style={styles.wrap}>
      <HardShadow offset={4} color={colors.red} style={styles.tilt}>
        <Pressable accessibilityRole="button" accessibilityLabel={`${label}. Show`} onPress={onPress} style={styles.banner}>
          <View style={styles.flag}>
            <Text style={styles.arrow}>↑</Text>
          </View>
          <MonoLabel size={12} tracking={0.14} color={colors.paper} style={styles.text}>
            {label}
          </MonoLabel>
        </Pressable>
      </HardShadow>
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', top: 12, left: 0, right: 0, alignItems: 'center', zIndex: 25 },
  tilt: { transform: [{ rotate: '-1.5deg' }] },
  banner: { flexDirection: 'row', alignItems: 'center', height: Math.max(40, minTap), backgroundColor: colors.ink },
  flag: { width: 44, height: '100%', alignItems: 'center', justifyContent: 'center', backgroundColor: colors.red },
  arrow: { fontFamily: fonts.monoBold, fontSize: 18, color: colors.onRed },
  text: { paddingHorizontal: 16 },
})
