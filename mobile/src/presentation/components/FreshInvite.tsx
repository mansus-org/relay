import { Pressable, Share, StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line, shadow } from '../theme'
import { HardShadow } from './HardShadow'
import { Stamp } from './Stamp'

type Props = {
  /** The link as it should be sent, token included. */
  link: string
  /** The token on its own, so it can be picked out of the link in a different colour. */
  token: string
}

/**
 * The invite that was just made, kept on screen until something else happens.
 *
 * The token is the whole secret and it is shown in full, once, here: not written to a file, not
 * kept after a refresh. The text is selectable, so a long press copies it without a clipboard
 * dependency, and Share hands it to whatever app the admin means to send it from.
 */
export function FreshInvite({ link, token }: Props) {
  const cut = token === '' ? -1 : link.indexOf(token)
  return (
    <HardShadow offset={shadow.regular} color={colors.red}>
      <View style={styles.card}>
        <View style={styles.stamp} pointerEvents="none">
          <Stamp label="Fresh" tone="ochre" />
        </View>
        <Text style={styles.label}>New invite</Text>
        <View style={styles.url}>
          <Text selectable accessibilityLabel={`Invite link. ${link}. Press and hold to copy.`} style={styles.urlText}>
            {cut < 0 ? link : link.slice(0, cut)}
            <Text style={styles.token}>{cut < 0 ? '' : token}</Text>
          </Text>
        </View>
        <View style={styles.buttons}>
          <ShareButton link={link} />
        </View>
      </View>
    </HardShadow>
  )
}

function ShareButton({ link }: { link: string }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Share this invite"
      onPress={() => {
        void Share.share({ message: link, title: 'Relay invite' }).catch(() => undefined)
      }}
      style={({ pressed }) => [styles.share, pressed && styles.pressed]}
    >
      <Text style={styles.shareText}>SHARE</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: line.strong,
    borderColor: colors.ink,
    paddingTop: 14,
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  stamp: { position: 'absolute', right: -8, top: -16 },
  label: { fontFamily: fonts.body, fontSize: 16, color: colors.ink },
  url: { marginTop: 10, padding: 12, backgroundColor: colors.ink },
  urlText: { fontFamily: fonts.monoBold, fontSize: 12.5, lineHeight: 18, color: colors.paper },
  token: { color: colors.ochre },
  buttons: { marginTop: 14 },
  share: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.ink,
    backgroundColor: colors.ink,
  },
  pressed: { backgroundColor: colors.ink2, borderColor: colors.ink2 },
  shareText: { fontFamily: fonts.monoBold, fontSize: 12.5, letterSpacing: 1.2, color: colors.paper, textAlign: 'center' },
})
