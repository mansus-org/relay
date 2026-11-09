# Relay — Product

> **Note:** written against the old Go node, which has been removed. The implementation is now [`backend/`](../backend/README.md) (FastAPI) and [`mobile/`](../mobile/README.md) (Expo); endpoint, CLI and file names below describe the old node and are kept as design context.

Relay is a **micro-social network for you and your real friends**: a small,
private-feeling social space that a group of friends runs on a server one of
them keeps. It is a virtual third place, not a platform.

It is for the group chat that wants somewhere to put things. Photos from a trip,
a link worth reading, a half-finished essay, a poster for a show, a page of
notes. Not a timeline that trains you to scroll. A place with addresses, rooms,
and people you actually know.

```
one node  →  4 to 29 friends  →  pages, posts, pictures, comments
```

## The problem, plainly

Group life keeps getting pushed into products. The photos are in one app, the
links in another, the long writing somewhere else, and the group's memory is
owned by a company that can change the rules, count everyone, or close the door.

Relay is the opposite arrangement: one program, one computer, one group. The
server belongs to someone in the group. The pages belong to the people who made
them. There is no company in the middle, no account to create, and no growth
target to satisfy.

## What Relay is

- **A node.** One Go binary on a computer the host controls. It serves the
  group's pages at real addresses under one hostname.
- **A guest list.** People join through invitation links, not sign-ups. An
  invitation is the identity. Members can invite people they vouch for, and the
  host can revoke a whole branch at once.
- **Communities.** A community is a named group inside the node: a book club, a
  street, a reading group. One with a place attached has an H3 cell and a radius
  around it, and asking for the communities near a cell gets back the ones whose
  radius reaches it. Anyone can read a community; a signed-in member can join one
  that reaches where they are, or one that is not about a place at all. A post can
  be filed to a community, and its members see all of them.
- **A home for posts.** Every member has a profile page listing what they have
  shared. The node's home page lists what everyone has shared, newest first.
- **Microwebsites.** A post is a small static website: HTML, pictures, links,
  a page of writing. Templates make the common kinds of post easy to create
  without a build step.
- **Comments.** Friends can talk under a post. There are no likes, reposts,
  follower counts, or recommendations. If you want to share something, you make
  your own post about it and link to it.

## What Relay is not

- **Not a public social network.** There is no global directory, no trending
  list, and no way to browse strangers' nodes. The one list that reaches past
  your own guest list is the communities near you: groups that chose a place and
  a radius, shown to someone standing inside it.
- **Not an account system.** There is no email, password, profile handle, or
  password reset. Your invitation is your way in.
- **Not a platform.** There is no company account, no ads, no tracking, no
  analytics product, and no engagement metric.
- **Not a publishing ideology.** Relay does not ask you to agree with a theory
  of the web. The point is the place, not a manifesto.
- **Not a replacement for the open web.** Posts are ordinary static files at
  ordinary URLs. You can link to them, back them up, and take them with you.
  Post scripts run sandboxed and cannot act as the node or the viewer.

## The shape of a node

A node has a name (`--name`), one public address, and a data directory. Its
pages live at:

```
https://relay.example.org/<node>/<post>/
```

The host keeps the machine running and makes invitations. Members publish,
comment, and invite people they trust. The host is not a moderator by default;
they are the person with the keys to the server. The plan for moderation is in
[`pivot-plan.md`](pivot-plan.md).

## Invitations are the whole account system

An invitation link carries a key. Opening it makes the browser a signed-in
member of that node. That is the account.

- The host creates the first invitations.
- Any member can create an invitation for someone else.
- An invitation can be revoked. Revoking a member also revokes everyone they
  invited.
- There is no password and no recovery. Lose the link and ask the host for a
  new one; the host rotates the key and gives you a fresh link.

The mechanics are in [`invites.md`](invites.md).

A planned convenience (not built) is a passkey for one-tap returning sign-in,
keeping the invitation as recovery and revocation — see
[`accounts.md`](accounts.md).

## Posts are microwebsites

Relay already hosts static sites. The pivot keeps that core and makes it social:

- A **post** is a site with an entry in the node's post index.
- A **profile** lists the posts of one member.
- The **home** lists the posts of everyone, newest first.
- A **template** is a small site that knows how to make a post. It provides a
  form (`prepublish.html`) and the code that turns the form into files
  (`publish.js`). Relay serves the form and accepts the finished files. It does
  not run template code on the server.

The template and publish contract is in [`publishing.md`](publishing.md).

## Vocabulary

| Word | Meaning |
|---|---|
| **Node** | This Relay installation, run by the host on one machine. |
| **Host** | The person who runs the node and holds the admin token. |
| **Member** | A person with a live invitation key on this node. |
| **Invite** | A link carrying a key. It is both the invitation and the identity. |
| **Post** | A static microwebsite plus its entry in the node's index. |
| **Template** | A kind of post: note, link, gallery, article, songs, videos, carousel, jet set radio, longform, reply, event, or one a member installs. |
| **Profile** | The page listing one member's posts. |
| **Home** | The page listing every member's recent posts, newest first. |
| **Comment** | A short reply under a post, visible to members. |
| **Community** | A named group inside the node, optionally anchored to a cell and a radius around it. |
| **Membership** | One person's join of one community. It can carry a pseudonym. |
| **Pseudonym** | The name someone chooses to be shown by in one community, instead of their own. |

## Relay and the IndieWeb

Relay sits in the IndieWeb / "small web" neighbourhood: the same "own your
data, small pieces loosely joined, no engagement mechanics" values as Are.na,
Cohost, Pixelfed, and Micro.blog. The difference is that Relay is **group-first**
— one node, one group, invitation as identity — where the IndieWeb is
domain-first. [`navigation-pivot.md`](navigation-pivot.md) §4.1 covers the
positioning; [`indieweb-syndication.md`](indieweb-syndication.md) and
[`indieauth.md`](indieauth.md) cover the mechanics (feeds, Webmention, Micropub,
IndieAuth). These are proposals, not built behaviour.

## Principles

1. **Small is the feature.** A node is a group, not an audience. The default
   ceiling is 29 members.
2. **Hosted by someone you know.** The server has a person behind it, not a
   support queue.
3. **No engagement mechanics.** Newest first. No likes, streaks, counts, or
   recommendations.
4. **The invitation is the account.** No passwords, no email, no recovery
   questions, no central user table.
5. **Posts are files.** Static by default, portable by nature, readable without
   Relay.
6. **Templates, not build tools.** A form and a preview, not a framework.
7. **The software has no politics.** People can use it for a club, a family, a
   reading group, a band, or a street. The reason to use it is the place it
   gives them.

## What success looks like

A group of friends can:

1. install one program on a spare computer,
2. send each other invitation links,
3. open the node and see each other's recent posts,
4. share a photo, a link, or a page of writing without reading a manual,
5. comment on each other's posts,
6. invite one more person they trust,
7. back up the whole node as one folder and move it to another machine.

Nothing in that list requires an account, a subscription, a cloud provider, or
an ideology.
