from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from photosort.config import settings
from photosort.models import User

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=30)

_hasher = PasswordHasher()
# Fixer Dummy-Hash (identische Kostenparameter wie echte Hashes, siehe _hasher oben) fuer die
# Anti-Enumeration-Verifikation bei unbekanntem Username in POST /auth/login. Bricht in
# tests/test_api_auth.py::test_login_with_unknown_username_still_runs_dummy_verification.
_DUMMY_PASSWORD_HASH = _hasher.hash("dummy-password-for-constant-codepath")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def verify_dummy_password(password: str) -> None:
    """Verifiziert gegen einen fixen Dummy-Hash, ohne das Ergebnis auszuwerten.

    Existiert ausschliesslich dafuer, dass der Login-Codepfad bei unbekanntem Username
    denselben Argon2-Verify-Aufwand betreibt wie bei einem existierenden User mit falschem
    Passwort (Anti-Enumeration gegen User-Enumeration).
    """
    try:
        _hasher.verify(_DUMMY_PASSWORD_HASH, password)
    except VerifyMismatchError:
        pass


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    # algorithms=[ALGORITHM] fixiert den erlaubten Algorithmus explizit - niemals aus dem
    # Token-Header uebernehmen oder weglassen (Algorithm-Confusion/"alg: none"). Bricht in
    # tests/test_security.py::test_decode_access_token_rejects_alg_none und
    # tests/test_auth_guard.py::test_protected_endpoint_rejects_alg_none_token.
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
