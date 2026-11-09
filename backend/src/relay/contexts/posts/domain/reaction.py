"""A reaction: one person's one emoji on one post."""

import unicodedata
from datetime import datetime
from uuid import UUID

from relay.shared.domain import ConflictError, Entity, NotFoundError, ValidationError, ValueObject

#: How long an emoji may be. The longest sequences people actually use - a family
#: joined with zero-width joiners, a skin tone, a keycap - stay well under this,
#: and everything above it is a word pretending to be an emoji.
MAX_EMOJI_LENGTH = 16


def as_one_emoji(emoji: str) -> str:
    """An emoji in the one form the server counts it in, however it was typed.

    Composed, so a sequence written with combining marks is the same emoji as the same
    sequence written whole. What is deliberately not touched is the variation selector
    that picks picture over text glyph: dropping it would fold "❤️" into "❤" and draw a
    line where someone chose a picture, so the same emoji sent in both forms counts
    twice. A client that offers an emoji offers it in one form.
    """
    return unicodedata.normalize("NFC", emoji)


class AlreadyReactedError(ConflictError):
    """That person has already reacted with that emoji."""


class ReactionNotFoundError(NotFoundError):
    """There is no such reaction to take back."""


class Reaction(Entity):
    """One person's one emoji on one post.

    The post, the person and the emoji together happen once; a second one of the
    same is the same opinion twice, so it is refused rather than counted twice.
    """

    post_id: UUID
    user_id: UUID
    emoji: str
    created_at: datetime

    @classmethod
    def given(cls, *, post_id: UUID, user_id: UUID, emoji: str, created_at: datetime) -> "Reaction":
        """React. The only way a reaction is made.

        What is stored is the emoji in the one form the server counts it in, so a
        reaction can be taken back with the emoji that came back in the response.
        """
        said = as_one_emoji(emoji.strip())
        if not said:
            raise ValidationError("A reaction needs an emoji.")
        if len(said) > MAX_EMOJI_LENGTH:
            raise ValidationError(f"An emoji is at most {MAX_EMOJI_LENGTH} characters.")
        if any(character.isspace() for character in said):
            raise ValidationError("A reaction is one emoji, not a phrase.")
        return cls(post_id=post_id, user_id=user_id, emoji=said, created_at=created_at)


class ReactionTally(ValueObject):
    """One emoji on one post, counted, with whether the reader is in that count."""

    emoji: str
    count: int
    user_reacted: bool = False
