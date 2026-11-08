"""bcrypt, the one place that touches it: slow is the point, and so is the shape."""

import pytest

from relay.contexts.auth.infrastructure.passwords import BcryptPasswordHasher


@pytest.fixture(scope="module")
def hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def test_the_same_password_hashes_twice_gives_two_answers(hasher: BcryptPasswordHasher) -> None:
    assert hasher.hash("hunter2222") != hasher.hash("hunter2222")


def test_the_password_it_agrees_with_is_the_one_it_was_given(hasher: BcryptPasswordHasher) -> None:
    stored = hasher.hash("hunter2222")

    assert hasher.verify("hunter2222", stored) is True
    assert hasher.verify("hunter2223", stored) is False


def test_an_account_that_does_not_exist_is_answered_like_a_wrong_password(
    hasher: BcryptPasswordHasher,
) -> None:
    assert hasher.verify("hunter2222", None) is False


def test_a_hash_this_code_never_wrote_is_a_no_rather_than_a_crash(
    hasher: BcryptPasswordHasher,
) -> None:
    assert hasher.verify("hunter2222", "not-a-bcrypt-hash") is False
