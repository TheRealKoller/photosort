from datetime import UTC, datetime, timedelta

import jwt
import pytest

from photosort.config import settings
from photosort.models import User
from photosort.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("wrong password", hashed) is False


def test_verify_dummy_password_does_not_raise() -> None:
    # Reine Codepfad-Absicherung: die Dummy-Verifikation muss immer durchlaufen,
    # unabhaengig vom uebergebenen Passwort, und darf nie eine Exception nach aussen lassen.
    verify_dummy_password("irgendein Passwort")
    verify_dummy_password("")


def test_create_and_decode_access_token_roundtrip() -> None:
    user = User(id=1, username="daniel", password_hash="irrelevant")

    token = create_access_token(user)
    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert payload["username"] == "daniel"


def test_decode_access_token_rejects_expired_token() -> None:
    payload = {
        "sub": "1",
        "username": "daniel",
        "exp": datetime.now(UTC) - timedelta(days=1),
        "iat": datetime.now(UTC) - timedelta(days=31),
    }
    expired_token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(expired_token)


def test_decode_access_token_rejects_wrong_signature() -> None:
    payload = {
        "sub": "1",
        "username": "daniel",
        "exp": datetime.now(UTC) + timedelta(days=30),
    }
    forged_token = jwt.encode(payload, "not-the-real-secret-key-value-x", algorithm=ALGORITHM)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged_token)


def test_decode_access_token_rejects_alg_none() -> None:
    payload = {
        "sub": "1",
        "username": "daniel",
        "exp": datetime.now(UTC) + timedelta(days=30),
    }
    none_alg_token = jwt.encode(payload, key="", algorithm="none")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(none_alg_token)
