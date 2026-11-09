# Relay Pivot — Implementation Plan

> **Note:** written against the old Go node, which has been removed. The implementation is now [`backend/`](../backend/README.md) (FastAPI) and [`mobile/`](../mobile/README.md) (Expo); endpoint, CLI and file names below describe the old node and are kept as design context.

**Status:** active plan. Phases 0–4 are done: cleanup, member session and
welcome, posts/profiles/home feed, comments, and templates. Phase 5 is not
built yet.

**New proposals (not built):** [`navigation-pivot.md`](navigation-pivot.md)
reopens decision 3.8 (public reading) and re-plans the front door (its visual
side is [`ui-ux-pivot.md`](ui-ux-pivot.md), with three home-feed mockups under
[`../ui-experiments/`](../ui-experiments/));
[`indieweb-syndication.md`](indieweb-syndication.md),
[`indieauth.md`](indieauth.md), and [`accounts.md`](accounts.md) extend the
plan toward the IndieWeb.

This plan turns the brief in [`pivot.md`](pivot.md) into ordered work. The
product definition is in [`product.md`](product.md). The two hard parts have
their own specs:

- invitations and member identity → [`invites.md`](invites.md)
- posts, templates, and the publish protocol → [`publishing.md`](publishing.md)

The current code is documented in [`product.md`](product.md) and
[`api.md`](api.md). Read those before changing code.

---

## 1. Goal and non-goals

### Goal

Turn Relay from "static site hosting by invite" into "a micro-social network for
you and your real friends", without losing the hosting core.

In one sentence:

> A node is one program on a friend's computer. It hosts a chronological,
> members-only-by-invitation home of microwebsites, profiles, and comments for
> a group of 4–29 people.

### Non-goals (for this pivot)

- Federation between nodes.
- A global directory or public profiles. Communities are the exception the
  tracker settled (RELY-89, 2026-11-09): there is a list of the communities whose
  radius reaches the cell you ask about, which is a locality filter over groups
  that chose to be findable, not a directory of people.
- Likes, reposts, follower counts, or an algorithmic feed.
- A native mobile app, push notifications, or real-time chat.
- Per-post privacy controls or encrypted posts.
- Email, passwords, OAuth, or account recovery.
- Migrating the server runtime to another language or framework.
- Running template JavaScript on the server.

If a proposal needs one of these to make sense, it is a different product.

---

## 2. Where we start

Built today (see [`product.md`](product.md)):

- one Go binary, standard-library HTTP server, one data directory
- static sites at `/<node>/<site>/`
- atomic tar uploads authenticated by per-member deploy keys
- last 10 versions and rollback
- invitation links with delegated invites and cascade revoke
- operator console at `/_relay/admin.html`
- a browser publish page and a small Markdown-to-page helper
- native TLS or a reverse proxy in front
- no database, no accounts, no social features

The gap to the goal is:

| Needed | Today |
|---|---|
| Member session that survives a page load | Invite token pasted into the publish form |
| Home feed of everyone's posts | None |
| Profile page per member | None |
| Post index (author, title, time) | Sites on disk, unattributed index only in `deploy-keys.json` |
| Comments | None |
| Template picker and publish flow | Free-form file upload / Markdown page |
| Member display names, bios | Invite label only |
| Moderation tools for the host | Revoke keys, rollback sites |

The hosting core is sound. We add a small social layer on top of it. We do not
rewrite the file serving, upload, or version machinery.

---

## 3. Locked decisions for the pivot

These are the choices the rest of the plan depends on. Reopen them only with a
written reason.

### 3.1 One node is one group

A node is not a public host. It is a group's server. The operator is the host,
not a platform administrator. The node name is the group's name.

Default member ceiling: **29**. The host may raise it with
`--max-members`, but the UI and docs are designed for a few dozen people, not
growth.

Reopened in part (RELY-89, 2026-11-09): a node also holds **communities** — named
groups with their own membership, feed, and optional locality. Joining one is
open to anyone signed in who stands inside its radius, which is a wider door than
an invitation. The node is still one group on one machine with one host, and the
ceiling above is about the node's own member list.

### 3.2 An invitation is the identity

There are no accounts. A live invitation key identifies a member. Opening an
invite link sets a member cookie. The browser is then signed in until the key
is revoked or the cookie is cleared. The token remains the credential for the
CLI and for AI assistants.

The full model, including cascade revoke and the cookie, is in
[`invites.md`](invites.md).

### 3.3 Posts are sites; the index is separate

The static site at `<data>/sites/<site>/` stays the source of truth for the
content. A small index records which member published it, when, under which
template, and with what title.

This keeps the existing deploy, rollback, and backup behavior. It also means a
post can always be read and moved without Relay.

### 3.4 The feed is chronological and small

The home page is every member's posts, newest first, grouped by day. There is no
ranking, no "for you", no popularity, and no read state. A node has few enough
posts that the group can simply see them.

No reposts. To share someone else's post, write your own post linking to it.

A community's feed is the same rule with one filter: the posts filed to that
community, newest first, removed posts left out (RELY-89). Distance is not a
read-time filter — a member sees their community's posts wherever they were
written from, and the radius is checked when they join.

### 3.5 Comments are members-only and plain

A comment is text by a member under a post. Markdown-lite is allowed (links,
emphasis, line breaks), sanitized on render. No images in comments in the first
version. No comment counts in the feed.

### 3.6 Templates run in the browser

Relay serves `prepublish.html` from the template and accepts the finished files
at `POST /_relay/v1/publish`. The template's `publish.js` runs in the member's
browser. Relay never executes template code on the server.

Rationale: no server-side sandbox, no arbitrary JS in the node process, and the
template can use ordinary browser APIs for previews. The trade-off is that a
template is trusted by the host before it is installed. Templates are not
downloaded from a public marketplace in this pivot.

### 3.7 Social metadata lives in small JSON stores

For a node of dozens of members, a database is unnecessary. We add:

- `posts.json` — the post index
- `comments.json` — comments, keyed by post
- `templates.json` — installed templates (or discovery from a directory)
- extended `deploy-keys.json` — members, invites, display names

All writes go through one in-process store with a mutex and atomic
temp-file-plus-rename. The store is an interface so a later SQLite
implementation can replace it without touching handlers. Backup remains "copy
the data directory".

### 3.8 Static sites are unlisted, not secret

Anyone with the URL can read a post. Only members can publish, comment, or see
the home page. We will say this plainly in the docs and UI. Per-post privacy is
a later product, not a hidden promise of the first version.

**Proposed reopening:** [`navigation-pivot.md`](navigation-pivot.md) §6.3 flips
this — the feed, profiles, and comment *reads* become public by default (the
content is already public at its URL), with `--members-only` as an opt-out.
Publishing and commenting stay invite-only.

### 3.9 The host can moderate

The host can:

- revoke a member (which also revokes their invite branch),
- hide or delete a post from the feed and profile,
- delete a comment,
- rotate an invite.

Revoking a member does not automatically delete their posts. The default is to
keep the group's history; the host can remove content explicitly. This is the
smallest moderation model that does not turn the host into a platform.

---

## 4. Target model

### 4.1 Entities

```
Node
  name, host, address, data dir, max members

Member
  id, display name, label, bio (optional), joined at, revoked, invited by
  credential: live invite token (hashed at rest)

Invite
  id, member id, token hash, created at, expires at (optional), revoked,
  invited by member id

Post
  id (= site name), member id, title, summary, template, site name,
  published at, updated at, hidden

Comment
  id, post id, member id, body, created at, deleted

Template
  id, name, description, version, folder, fields, built-in or installed
```

### 4.2 Data directory

```
<data>/
  admin-token
  deploy-keys.json              members, invites, site attribution
  posts.json             post index
  comments.json          comments by post
  templates.json         installed template metadata (optional cache)
  sites/
    <site>/              live microwebsite (static files)
    .versions/<site>/<id>/
  templates/
    <template>/          prepublish.html, publish.js, relay-template.json, assets
```

Storing `posts.json` and `comments.json` separately from `deploy-keys.json` keeps
identity and content independently replaceable. A future SQLite store can
implement the same interface.

### 4.3 Routes

Current hosting routes stay:

```
GET  /                                          public landing
GET  /<node>/<site>/...                         static post
GET  /_relay/admin.html                         host console
GET  /_relay/publish.html                       publish page
POST /_relay/v1/sites/<site>/deploy             tar upload (member bearer)
```

New social routes:

```
GET  /_relay/home.html                          member home (cookie required)
GET  /_relay/people/<member>                    member profile
GET  /_relay/posts/<site>                       post wrapper + comments
POST /_relay/v1/session                         exchange invite token for cookie
DELETE /_relay/v1/session                       sign out
GET  /_relay/v1/me                              current member
GET  /_relay/v1/feed                            home feed JSON
GET  /_relay/v1/people/<member>/posts           profile posts JSON
GET  /_relay/v1/posts/<site>                    post metadata
GET  /_relay/v1/posts/<site>/comments           comments (members only)
POST /_relay/v1/posts/<site>/comments           add comment
DELETE /_relay/v1/comments/<id>                 delete own comment (host: any)
POST /_relay/v1/publish                         publish from a template
GET  /_relay/v1/templates                       list templates
GET  /_relay/templates/<name>/prepublish.html   template form
```

`GET /` remains the public landing for logged-out visitors. A member who wants
their home opens `/_relay/home.html`, or the invite link redirects there.

The Python backend has grown its own routes since this plan was written. The
communities API (RELY-89) is the current shape for groups:

```
GET    /api/communities?cell=<h3>           communities whose radius reaches <h3>
POST   /api/communities                     create (auth)
GET    /api/communities/{id}
GET    /api/communities/{id}/feed?cursor=   {posts, next_cursor}
POST   /api/communities/{id}/join           {cell, pseudonym?} (auth)
```

The complete current and planned wire shapes are in [`api.md`](api.md).

### 4.4 Publish flow

1. Member opens the publish page or a template directly.
2. The node serves `prepublish.html` from the template folder.
3. The template renders fields and a preview, using `publish.js`.
4. On submit, `publish.js` produces `{ title, summary, site, files[] }`.
5. The browser posts it to `/_relay/v1/publish` with the member cookie (or the
   invite token as a bearer token for non-browser clients).
6. The node validates the member, template, paths, size, and names, writes the
   site atomically, snapshots the previous version, and appends to `posts.json`.
7. The member lands on `/_relay/posts/<site>`.

The current tar endpoint remains for power users, the CLI, and AI assistants. A
plain upload without metadata becomes a post with a title derived from the site
name and `template: "custom"`.

### 4.5 Comment flow

1. A member opens the post wrapper, which fetches
   `GET /_relay/v1/posts/<site>/comments`.
2. The member writes a comment and posts it with the cookie.
3. The node escapes and validates the body, appends it to `comments.json`, and
   returns the sanitized HTML view.
4. The wrapper renders it. Non-members see a "members only" note instead of the
   form.
5. A member can delete their own comment; the host can delete any.

The wrapper at `/_relay/posts/<site>` is the comment surface. Static posts are
CSP-sandboxed so their scripts cannot call member APIs with the viewer's cookie;
that is why comments are not embedded inside the post itself.

An embeddable panel is deferred until there is an isolated embed origin or a
scoped comment token. A post script must not be able to act as the signed-in
member.

---

## 5. Phases

Each phase is independently shippable and leaves the node working. Estimates
are for one developer who knows the codebase; they are ordering devices, not
promises.

### Phase 0 — Cleanup and a real front door (this refactor)

**Status: done.**

- Remove the old manifesto, review, tunnel/classifier/API-contract drafts, and
  the mock node/site consoles.
- Rewrite the public landing page around the third-place product.
- Rewrite the technicals page, README, user guide, deploy skill, and frontend
  skill so they describe the actual code and the pivot.
- Add the product definition, this plan, and the invites/publishing/architecture
  specs.

**Acceptance:** `make check` passes; no page or doc points at a deleted file or
an unbuilt feature as if it were live.

### Phase 1 — Member session and welcome

**Status: implemented.** The session API, member cookie, welcome page, invite
exchange, and display name/bio editing are in the code. The feed placeholder is
intentional; the feed itself is Phase 2.

**Goal:** opening an invite makes the browser a member without pasting the key
on every visit.

Work:

- Add `POST /_relay/v1/session` and `DELETE /_relay/v1/session`.
- Set an `HttpOnly`, `SameSite=Lax`, `Secure`-when-TLS cookie with the invite
  token (hashed lookup stays server-side).
- Add `GET /_relay/v1/me`.
- Add `/_relay/home.html`: a member-only shell with the welcome copy, a
  publish button, a sign-out action, and a placeholder for the feed.
- The invite link opens `/_relay/home.html#key=…`; a tiny script exchanges the
  fragment for a cookie and strips the fragment from the URL.
- Keep the current publish page working; it should detect the cookie and hide
  the key field.
- Existing links point at `/_relay/publish.html#key=…`. Keep them valid: the
  publish page performs the same exchange and then offers the home. Never
  invalidate invitation links that have already been sent.
- Mark revoked keys as unusable everywhere; clear the cookie on 401.
- Add display name and optional bio fields to the member record. Keep the
  existing `user` label as the stable id.

Do not build the feed yet. The home can show "Your people will appear here."

**Acceptance (met):**

1. A fresh invite opens the home, sets a cookie, and survives a reload.
2. A revoked invite gets a clear "not valid or has been revoked" message.
3. Sign-out clears the cookie.
4. The publish page works without asking for the key again, and existing
   `publish.html#key=…` links still establish the session.
5. No token appears in a URL after the exchange completes.

### Phase 2 — Posts, profiles, and the home feed

**Status: implemented.** A deploy indexes a post and writes `relay-post.json`;
the home feed, profile pages, post wrappers, and `relay index` backfill are in
the code.

**Goal:** every published site becomes a post with an author and a place in the
group's home.

Work:

- Add the `posts.json` store and a `Post` model.
- On deploy and on template publish, upsert a post record: site, member, title,
  summary, template, published/updated time, hidden.
- Derive a title from the site name for plain uploads; allow an explicit title
  in the publish request and in `relay-post.json`.
- Add `GET /_relay/v1/feed`, `GET /_relay/v1/posts/<site>`, and
  `GET /_relay/v1/people/<member>/posts`.
- Add `/_relay/posts/<site>`: title, author, date, an iframe of the real static
  site, and the comments slot.
- Add `/_relay/people/<member>`: display name, bio, and the member's posts,
  newest first.
- Build the home feed: chronological, newest first, cursor-paginated infinite
  scroll, author name, title, summary, cover image, template label. No counts.
- Add a backfill command for existing sites:
  `relay index --data <dir>` assigns unindexed sites to the host or leaves them
  unlisted. Existing keys' `sites` map is the best available attribution.
- The publish page shows "Live at …" and links to the post wrapper.

**Acceptance (met):**

1. Publishing a file or a Markdown page creates a post and shows it on the home.
2. The member's profile lists only their posts.
3. A second member's posts appear on the home but not on the first profile.
4. A rollback does not create a second post; it updates the same site.
5. Existing sites can be backfilled with `relay index --data <dir>`.
6. The feed is stable newest-first and has no popularity ordering.

### Phase 3 — Comments

**Status: implemented.** Comments, member-only read/write, host deletion, inline
comments under every feed/profile post, and the post-wrapper UI are in the code.
The embeddable panel is deferred: static posts are CSP-sandboxed, so comments
live on trusted member pages.

**Goal:** friends can reply under a post.

Work:

- Add the `comments.json` store with atomic writes.
- Add `GET`/`POST /_relay/v1/posts/<site>/comments` and
  `DELETE /_relay/v1/comments/<id>`.
- Require a live member cookie for read and write; return 401 otherwise.
- Sanitize comment HTML on render; allow links, emphasis, and paragraphs only.
- Add the comment UI to the post wrapper. (The embeddable panel is deferred
  until there is an isolated embed origin or a scoped token; a post script must
  not be able to call member APIs with the viewer's cookie.)
- Add delete-own-comment; host delete via the admin console.
- Cap comment length (2,000 characters) and rate-limit per member in memory.
- Do not show comment counts in the feed yet.

**Acceptance (met):**

1. Two members can comment under one post and see each other's comments.
2. A non-member gets the members-only note, not the form.
3. A revoked member cannot comment.
4. A member can delete their own comment; another member cannot.
5. The host can delete any comment from the admin console.
6. A comment with a script tag renders as text, never as markup.

### Phase 4 — Templates and the publish endpoint

**Status: implemented.** Nine built-in templates (Note, Link, Gallery,
Article, Songs, Videos, Images carousel, Jet Set Radio, Longform), the template
picker, the browser-side publish flow, the `/_relay/v1/publish` endpoint, and
template install/remove (member tar or host folder) are in the code. Built-ins are discovered from one
embedded folder tree, not a hardcoded list.

**Goal:** a non-technical member can make a good-looking post without touching
HTML.

Work:

- Define the template package and `relay-template.json` manifest (see
  [`publishing.md`](publishing.md)).
- Ship nine built-in templates: **Note**, **Link**, **Gallery**, **Article**,
  **Songs**, **Videos**, **Images carousel**, **Jet Set Radio**, **Longform**.
  Each is a small site folder with `prepublish.html`, `publish.js`, styles, and
  a manifest.
- Add template discovery: built-ins embedded in the binary plus templates in
  `<data>/templates/`.
- Add `GET /_relay/v1/templates` and the template picker on the publish page.
- Add `POST /_relay/v1/publish` with JSON `{template, title, summary, site,
  files[]}`.
- Validate member, template, file count, total bytes, path traversal, and site
  naming. Reuse the uploader's archive rules and version snapshot.
- Generate the post's comments snippet and `relay-post.json` on publish.
- Keep the tar endpoint for custom sites and assistants.
- Add a host action to install/remove a template (copy a folder, no public
  marketplace). The `relay template` command implements it.

**Acceptance (met):**

1. A member opens a template, fills the form, previews, and publishes.
2. The generated site has the template's look and the member's content.
3. The post appears on the home and profile.
4. A template cannot write outside its site or exceed the size cap.
5. Publishing with a revoked key fails.
6. A plain tar upload still works and appears as a custom post.
7. Built-in templates survive a node upgrade.

### Phase 5 — Host operations and polish

**Goal:** a host can run a node for a year without a surprise.

Work:

- `relay export` produces one archive of the data directory with a manifest.
- Document restore and upgrade. Add a `relay backup` convenience wrapper if it
  earns its place.
- Add member display-name editing and an invite chain view to the admin console.
- Add invite expiry (optional, default never) and a revoke-branch confirmation.
- Add simple node stats for the host only: members, posts, comments, disk use.
  No visitor tracking.
- Add a first-run setup screen: node name, host display name, first invite.
- Add limits: `--max-members`, `--max-post-bytes`, comment length, per-member
  rate limits.
- Write the moderation page in the user guide.
- Run a real group on a node for two weeks; fix the friction found.

**Acceptance:**

1. A non-developer host can install, invite, publish, comment, back up, and
   restore by following [`../users-guide.md`](../users-guide.md).
2. A backup restored on a fresh machine serves the same posts and comments.
3. The home and profiles survive a node restart and an upgrade.
4. The host can explain what is public and what is members-only.

---

## 6. Migration and compatibility

### Existing keys

`deploy-keys.json` already has `id`, `user`, `token`, `hash`, `created`, `revoked`,
and `invitedBy`. Treat each live key as a member. Add optional fields with
defaults:

- `displayName` — defaults to the part after the last `/` in `user`
- `bio` — empty
- `joinedAt` — defaults to `created`

Do not migrate tokens. Existing invite links keep working.

### Existing sites

`deploy-keys.json` already records a `sites` map (site → user label). Use it to
backfill `posts.json`:

- member = the key whose user matches the label, if there is exactly one live
- title = site name with hyphens replaced by spaces, title-cased
- template = `custom`
- publishedAt = the site directory's modification time

Sites with no attribution are left unlisted until the host assigns them. Do not
delete or rewrite any site content.

### Existing public pages

The landing page and technicals page keep their paths (`/`, `/index.html`,
`/technicals.html`, `/styles.css`). `manifesto.html` is removed; any external
link to it should be redirected to the landing page for a release or two, then
dropped. The node currently embeds the public site; update the embed list in the
same change that removes the file.

### Existing UI

`web/node.html` and `web/site.html` were mock consoles polling endpoints that
the node never served. They are removed. The operator console (`admin.html`),
publish page, and deploy page stay.

---

## 7. Risks and open questions

| # | Risk / question | Current stance |
|---|---|---|
| 1 | **Static posts are public by URL.** | Documented as unlisted, not secret. No per-post privacy in this pivot. Post scripts run under a CSP sandbox so they cannot call member APIs with the viewer's cookie. |
| 2 | **An invite link is a bearer credential.** Anyone with the link is the member. | Treat links like passwords; rotate on leak. Optional expiry in Phase 5. |
| 3 | **Plaintext tokens in `deploy-keys.json`.** The console reveals them. | Keep for now so hosts can re-copy links. Phase 5 should move to hashed-only plus rotation. |
| 4 | **Template code runs in the member's browser on the node origin.** | Templates are installed by the host and trusted. Do not add a public marketplace in this pivot. |
| 5 | **Comments and posts are stored in JSON rewritten atomically.** | Fine for dozens of members. The store interface allows SQLite later. Measure before changing. |
| 6 | **Moderation is minimal.** | Host revokes members and removes content explicitly. Write it in the guide; do not pretend the node is a safe public space. |
| 7 | **No account recovery.** | A lost invite is a host rotation. This is the price of no accounts. |
| 8 | **The node address can change.** | Posts are relative-path sites; a moving node changes the origin. Export/restore is the migration path. |
| 9 | **Invite chain abuse.** | Members can invite; cascade revoke contains a bad branch. Host can lower `--max-members`. |
| 10 | **Do we need a `relay-post.json` sidecar?** | Yes: it keeps a post's metadata with its files, so an export is readable without `posts.json`. The index remains authoritative for ordering. |
| 11 | **Does the home need pagination?** | Not at 29 members. Add a "older" link only if real use demands it. |
| 12 | **Should profiles be sites too?** | No in this pivot. A profile is a generated page from member data and the post index. A member can still publish a custom "about" post. |

---

## 8. Definition of done for the pivot

A group can run Relay for a month and say:

- "I know where our things are."
- "I know who is in the group."
- "I can put something up without asking a developer."
- "I can comment on my friend's post."
- "The host can back it up."
- "Nobody is counting us."

If a feature does not serve one of those sentences, it waits.
