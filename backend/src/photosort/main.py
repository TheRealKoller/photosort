from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from photosort.api import auth, opencloud, photos, projects, ratings
from photosort.config import settings
from photosort.rate_limit import limiter

# Muss-Kriterium (specs/features/0006-auth.md, architecture/0003-securitykonzept.md): ein
# Signing-Secret, das dem oeffentlich bekannten Platzhalter entspricht oder zu kurz ist, erlaubt
# beliebige JWT-Faelschung - vollen Zugriff auf beide Accounts und damit transitiv auf alle
# Familienfotos.
MIN_SECRET_KEY_LENGTH = 32
PLACEHOLDER_SECRET_KEY = "change-me"


def _handle_rate_limit_exceeded(request: Request, exc: Exception) -> Response:
    # Duenner, typgenauer Wrapper: FastAPIs add_exception_handler erwartet einen Handler fuer
    # Exception, slowapis eigener Handler ist praeziser auf RateLimitExceeded typisiert (mypy
    # --strict wuerde die direkte Uebergabe sonst als Signatur-Mismatch ablehnen).
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


def create_app() -> FastAPI:
    if (
        settings.secret_key == PLACEHOLDER_SECRET_KEY
        or len(settings.secret_key) < MIN_SECRET_KEY_LENGTH
    ):
        raise RuntimeError(
            "settings.secret_key muss gesetzt sein: darf nicht dem Platzhalter 'change-me' "
            f"entsprechen und muss mindestens {MIN_SECRET_KEY_LENGTH} Zeichen lang sein "
            "(siehe .env.example)."
        )

    app = FastAPI(title="PhotoSort API")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)
    app.add_middleware(SlowAPIMiddleware)
    # Muss-Kriterium (specs/features/0005-minimal-project-frontend.md,
    # architecture/0003-securitykonzept.md): ohne diese Middleware koennte jede Website im
    # selben Netzwerksegment Anfragen an die API stellen, sobald ein Browser-Frontend existiert.
    # Nur die konfigurierten Frontend-Origins, kein Wildcard "*". allow_credentials bleibt False
    # (Default) - Token-Transport laeuft ueber den Authorization-Header, nie ueber Cookies
    # (decisions/0005-auth-implementation.md), daher nicht noetig.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(opencloud.router)
    app.include_router(projects.router)
    app.include_router(photos.router)
    app.include_router(ratings.router)

    return app


app = create_app()
