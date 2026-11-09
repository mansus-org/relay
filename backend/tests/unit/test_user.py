"""A username, a password and a display name: what an account is made of."""

import pytest

from relay.contexts.auth.domain.user import (
    MAX_DISPLAY_NAME_CHARS,
    MAX_PASSWORD_BYTES,
    DisplayName,
    InvalidDisplayNameError,
    InvalidPasswordError,
    InvalidUsernameError,
    Password,
    User,
    Username,
)


def test_a_username_is_folded_to_lowercase_and_stripped_of_its_padding() -> None:
    assert str(Username.parse("  Ada.Lovelace ")) == "ada.lovelace"


def test_two_spellings_of_one_handle_are_one_handle() -> None:
    assert Username.parse("ADA_love") == Username.parse("ada_love")


def test_a_dash_is_a_fine_character_in_a_handle() -> None:
    assert str(Username.parse("ada-lovelace")) == "ada-lovelace"


@pytest.mark.parametrize(
    "raw", ["ad", "a" * 21, "ada lovelace", "ada@lovelace", "ada\u00f1a", "", "   "]
)
def test_a_username_someone_could_not_type_is_refused(raw: str) -> None:
    with pytest.raises(InvalidUsernameError):
        Username.parse(raw)


def test_a_password_shorter_than_eight_characters_is_refused() -> None:
    with pytest.raises(InvalidPasswordError):
        Password.parse("short")


def test_a_password_beyond_what_bcrypt_reads_is_refused_rather_than_quietly_cut() -> None:
    with pytest.raises(InvalidPasswordError):
        Password.parse("x" * (MAX_PASSWORD_BYTES + 1))


def test_a_password_is_counted_in_bytes_because_that_is_where_bcrypt_stops() -> None:
    # Forty of these is forty characters and eighty bytes: bcrypt would read half of it
    # and swear the rest was the wrong password.
    with pytest.raises(InvalidPasswordError):
        Password.parse("\u00e9" * 40)


def test_a_display_name_cannot_be_blank() -> None:
    with pytest.raises(InvalidDisplayNameError):
        DisplayName.parse("   ")


def test_a_display_name_is_one_line_and_says_so() -> None:
    with pytest.raises(InvalidDisplayNameError):
        DisplayName.parse("Ada\nLovelace")


def test_a_display_name_with_a_space_nobody_types_is_still_one_line() -> None:
    """Only a line break makes it two lines. A pasted non-breaking space is still a name."""
    assert DisplayName.parse("Ada\u00a0Lovelace").value == "Ada\u00a0Lovelace"


def test_a_display_name_is_capped_at_one_line() -> None:
    assert len(DisplayName.parse("x" * MAX_DISPLAY_NAME_CHARS).value) == MAX_DISPLAY_NAME_CHARS
    with pytest.raises(InvalidDisplayNameError):
        DisplayName.parse("x" * (MAX_DISPLAY_NAME_CHARS + 1))


def test_someone_who_skipped_the_display_name_is_called_by_their_handle() -> None:
    user = User(
        id=1,
        username=Username(value="ada"),
        display_name=DisplayName(value=""),
        password_hash="hashed:hunter2222",
    )

    assert user.name == "ada"


def test_an_account_from_a_request_carries_its_values_and_no_id_yet() -> None:
    user = User.new(username="ada", display_name="Ada L.", password_hash="hashed:hunter2")
    assert user.id is None
    assert user.name == "Ada L."
    assert user.is_admin is False
