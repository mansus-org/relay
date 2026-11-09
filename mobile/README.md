# Relay mobile

Expo (SDK 58) / React Native app, TypeScript strict, Expo Router. Design: `.pi/skills/relay-mobile-design`.

## Run

```sh
cd mobile
npm install
npx expo start      # then press i (iOS simulator) or a (Android emulator)
```

The server URL defaults to `https://relay.mansus.org` (changing it from the UI is planned for settings)
(stored in AsyncStorage as `relay_server_url`, applied on the next request).

## Layout

- `app/` file-based routes, kept thin: `_layout.tsx` (`AppProviders`), `(auth)/login`, `(auth)/join`, `(app)/index`,
  `(app)/communities/index` (nearby list), `(app)/communities/[id]` (feed + about), `(app)/communities/new`,
  `(app)/post/[id]` (one post, and what was said under it)
- `src/` is layered (see Architecture below)
- `assets/icon.svg` is the icon source; `npm run icons` regenerates the PNGs in `assets/` (iOS icon, Android adaptive foreground/background/monochrome, splash, favicon)
- Tokens live in SecureStore (`access_token`, `refresh_token`). The postal code the web feed last read is in AsyncStorage as `relay.postal_code.v1`. Auth, feed, post and community endpoint paths are constants in `src/infrastructure/http/endpoints.ts`.
The backend serves the place lookup and `/health` (RELY-79), posts, replies and reactions (RELY-90) and the live
`/stream` (RELY-91); anything past those is still proven against the fakes in `src/testing`.
- The feed asks for a place differently per platform: both ask where they are first — native the device, web the browser (`navigator.geolocation`, https only) — and whatever cannot answer falls back to a Spanish postal code (Galicia first). That empty state is `src/presentation/components/PostalCodePrompt.tsx`, driven by the `ask` phase of `useFeed`.

## Architecture

```
src/domain/          immutable types, pure functions, Result, and the ports (small interfaces)
src/application/     use cases: factories that take their ports as arguments
src/infrastructure/  adapters implementing the ports (axios client, SecureStore, AsyncStorage)
src/presentation/    React contexts and hooks that call use cases; theme
src/composition/     composition root: wires adapters into use cases, provides them to the UI
src/testing/         in-memory fakes shared by tests
```

Dependency rule: `domain` <- `application` <- `infrastructure` / `presentation`. `domain` imports nothing from
the other layers (and no React, axios or expo); `application` imports only `domain`; `infrastructure` and
`presentation` never import each other. `composition` is the only place that knows concrete adapters.
`src/__tests__/architecture.test.ts` enforces this.

Dependency injection is by closure, not by class or container: a factory takes its dependencies as one
argument and returns the function(s) it implements.

```ts
export const makeLogin =
  ({ authRepository, tokenWriter, serverUrlWriter }: Deps) =>
  async (input: LoginInput): Promise<Result<User, AuthError>> => { /* ... */ }
```

- Depend on the narrowest port (`TokenReader` vs `TokenWriter`, `ServerUrlReader` vs `ServerUrlWriter`).
- Errors are values (`Result<T, AuthError>`); adapters translate library errors at the boundary.
- No module-level mutable state outside `composition`; per-instance state (e.g. the single-flight refresh) lives in the factory closure.
- Tests build use cases with the fakes in `src/testing`; `composition/__tests__` wires the real adapters over in-memory storage and a fake axios adapter.
- To add a feature: port in `domain`, use case in `application`, adapter in `infrastructure`, wiring in `composition/wire-use-cases.ts`, expose via `UseCases`.

## Checks

```sh
npm run lint
npm test
npm run typecheck
npx expo-doctor
npx expo export --platform ios --platform android   # bundle check; dist/ is ignored
```
