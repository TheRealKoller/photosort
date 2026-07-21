from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_session
from photosort.models import User
from photosort.rate_limit import limiter
from photosort.security import create_access_token, verify_dummy_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Bewusst identischer, dokumentierter Wortlaut fuer "unbekannter User" und "falsches Passwort"
# (Anti-Enumeration, siehe specs/features/0006-auth.md).
INVALID_CREDENTIALS_DETAIL = "Ungültige Anmeldedaten"

_MAX_LOGIN_FIELD_LENGTH = 128


class LoginRequest(BaseModel):
    username: str = Field(max_length=_MAX_LOGIN_FIELD_LENGTH)
    password: str = Field(max_length=_MAX_LOGIN_FIELD_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS_DETAIL
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,  # von slowapi benoetigt (siehe @limiter.limit oben), sonst ungenutzt
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None:
        # Anti-Enumeration: auch bei unbekanntem Username laeuft eine Argon2-Verifikation mit
        # identischen Kostenparametern, damit der Codepfad (nicht die Wall-Clock-Zeit) fuer
        # beide Faelle gleich aussieht.
        verify_dummy_password(payload.password)
        raise _invalid_credentials()

    if not verify_password(payload.password, user.password_hash):
        raise _invalid_credentials()

    token = create_access_token(user)
    return TokenResponse(access_token=token, token_type="bearer")
