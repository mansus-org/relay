import { useRouter } from 'expo-router'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import type { LoginInput, RegisterInput } from '../application'
import type { AuthError, Result, User } from '../domain'
import { useUseCases } from './use-cases'

type AuthContextValue = {
  user: User | null
  isLoading: boolean
  login: (input: LoginInput) => Promise<Result<User, AuthError>>
  register: (input: RegisterInput) => Promise<Result<User, AuthError>>
  logout: () => Promise<void>
  /** The node kept a new name for you; the session has to stop showing the old one. */
  renamed: (displayName: string) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { login: loginUseCase, register: registerUseCase, logout: logoutUseCase, restoreSession, sessionEvents } = useUseCases()
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(
    () =>
      sessionEvents.onExpired(() => {
        setUser(null)
        router.replace('/login')
      }),
    [sessionEvents, router],
  )

  useEffect(() => {
    let cancelled = false
    void restoreSession()
      .then((restored) => {
        if (!cancelled && restored) setUser(restored)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [restoreSession])

  const login = useCallback(
    async (input: LoginInput) => {
      const result = await loginUseCase(input)
      if (result.ok) setUser(result.value)
      return result
    },
    [loginUseCase],
  )

  const register = useCallback(
    async (input: RegisterInput) => {
      const result = await registerUseCase(input)
      if (result.ok) setUser(result.value)
      return result
    },
    [registerUseCase],
  )

  const logout = useCallback(async () => {
    await logoutUseCase()
    setUser(null)
  }, [logoutUseCase])

  const renamed = useCallback((displayName: string) => setUser((current) => (current ? { ...current, name: displayName } : current)), [])

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout, renamed }),
    [user, isLoading, login, register, logout, renamed],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
