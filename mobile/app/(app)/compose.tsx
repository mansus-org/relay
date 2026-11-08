import { useRouter } from 'expo-router'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TextInput, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { charsLeft, FEED_RADIUS_KM, MAX_POST_LENGTH, type ComposeError } from '../../src/domain'
import { useAuth } from '../../src/presentation/auth'
import { Alert } from '../../src/presentation/components/Alert'
import { Avatar } from '../../src/presentation/components/Avatar'
import { Button } from '../../src/presentation/components/Button'
import { Chip } from '../../src/presentation/components/Chip'
import { GeoSun, GeoWedge } from '../../src/presentation/components/Geo'
import { MonoLabel } from '../../src/presentation/components/MonoLabel'
import { NavBar } from '../../src/presentation/components/NavBar'
import { colors, fonts, line } from '../../src/presentation/theme'
import { useCompose } from '../../src/presentation/use-compose'

const messages: Partial<Record<ComposeError, string>> = {
  empty: 'Write something first.',
  'too-long': `Posts are limited to ${MAX_POST_LENGTH} characters.`,
  network: 'Could not reach the server. Check your connection and try again.',
}

export default function Compose() {
  const router = useRouter()
  const { user } = useAuth()
  const { bottom } = useSafeAreaInsets()
  const compose = useCompose()
  const left = charsLeft(compose.body)
  const canPost = compose.body.trim() !== '' && left >= 0

  const close = () => (router.canGoBack() ? router.back() : router.replace('/'))
  async function post() {
    if (canPost && (await compose.submit())) close()
  }

  const where = compose.location ? (compose.location.placeName ?? 'Current location') : null

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <NavBar
        title="New post"
        subtitle={where ? `Within ${FEED_RADIUS_KM} km of ${where}` : 'Private to node members'}
        onCancel={close}
        action={<Button size="sm" label={compose.busy ? 'Posting…' : 'Post'} onPress={() => void post()} busy={compose.busy} disabled={!canPost} />}
        decoration={
          <>
            <GeoSun size={120} right={-30} top={52} />
            <GeoWedge size={130} flip right={22} top={92} />
          </>
        }
      />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: bottom + 24 }]} keyboardShouldPersistTaps="handled">
        {compose.error ? <Alert message={messages[compose.error] ?? 'Could not post. Try again.'} /> : null}
        <View style={styles.editor}>
          <Avatar name={user?.name ?? '?'} seed={user?.id} />
          <TextInput
            accessibilityLabel="Post text"
            style={styles.input}
            value={compose.body}
            onChangeText={compose.setBody}
            placeholder="What's happening nearby?"
            placeholderTextColor={colors.ink2}
            selectionColor={colors.red}
            multiline
            autoFocus
            maxLength={MAX_POST_LENGTH}
            textAlignVertical="top"
          />
        </View>
        <View style={styles.meter}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.min(100, (compose.body.length / MAX_POST_LENGTH) * 100)}%` }]} />
          </View>
          <MonoLabel
            size={12}
            tracking={0.06}
            color={left <= 40 ? colors.redText : colors.ink2}
            accessibilityLiveRegion="polite"
            accessibilityLabel={`${left} characters left`}
          >
            {`${compose.body.length} / ${MAX_POST_LENGTH}`}
          </MonoLabel>
        </View>
        <View style={styles.options}>
          <View style={styles.option}>
            <MonoLabel style={styles.optionLabel}>Where</MonoLabel>
            {compose.location ? (
              <Chip tone="red" label={where!} suffix="✕" accessibilityLabel={`Location ${where}. Tap to remove`} onPress={compose.clearLocation} />
            ) : (
              <Chip label="Add location" suffix="+" onPress={() => void compose.addLocation()} accessibilityState={{ selected: false }} />
            )}
          </View>
          {compose.communities.length > 0 ? (
            <View style={styles.option}>
              <MonoLabel style={styles.optionLabel}>Community</MonoLabel>
              <View style={styles.chips}>
                {compose.communities.map((c) => (
                  <Chip
                    key={c.id}
                    label={c.name}
                    tone={compose.communityId === c.id ? 'on' : 'plain'}
                    accessibilityState={{ selected: compose.communityId === c.id }}
                    onPress={() => compose.toggleCommunity(c.id)}
                  />
                ))}
              </View>
            </View>
          ) : null}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { paddingHorizontal: 20, paddingTop: 16 },
  editor: { flexDirection: 'row', gap: 12, marginTop: 18 },
  input: { flex: 1, minHeight: 112, padding: 0, fontFamily: fonts.body, fontSize: 19, lineHeight: 27, color: colors.ink },
  meter: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 },
  track: { flex: 1, height: 6, backgroundColor: colors.paper2 },
  fill: { height: 6, backgroundColor: colors.ink },
  options: { marginTop: 14, paddingTop: 14, gap: 12, borderTopWidth: line.regular, borderTopColor: colors.ink },
  option: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  optionLabel: { width: 96, paddingTop: 10 },
  chips: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
})
