import { Redirect, Stack, usePathname } from 'expo-router'
import { Platform } from 'react-native'

import { useAuth } from '../../src/presentation/auth'
import { authRedirect } from '../../src/presentation/auth-guard'

export default function AppLayout() {
  const { user, isLoading } = useAuth()
  const pathname = usePathname()
  if (isLoading) return null
  // The web build is the public surface: anyone with the address reads it. The installed app is
  // something you join, so it still opens on the login screen.
  const href = authRedirect({
    group: 'app',
    pathname,
    signedIn: !!user,
    isLoading,
    anonymousReading: Platform.OS === 'web',
  })
  if (href) return <Redirect href={href} />
  return <Stack screenOptions={{ headerShown: false }} />
}
