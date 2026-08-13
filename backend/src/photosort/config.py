from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://photosort:photosort@localhost:5432/photosort"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    opencloud_base_url: str = ""
    opencloud_username: str = ""
    opencloud_app_token: str = ""
    opencloud_drive_name: str = ""

    # Lokaler Verarbeitungs-Cache fuer Thumbnails (specs/features/0002-manual-categorization.md),
    # ueber das "photo_cache"-Docker-Volume auf backend/worker gemountet (docker-compose.yml).
    photo_cache_dir: str = "/data/photo-cache"

    # Initiale Benutzerkonten fuer die Seed-Migration (specs/features/0006-auth.md). Die
    # Usernamen-Platzhalter sind bewusst unterschiedlich: identische Defaults wuerden bei
    # unveraendertem .env dazu fuehren, dass die idempotente Seed-Migration nur EINEN statt
    # zwei Accounts anlegt (seed_user() findet den zweiten Username bereits vor und ueberspringt
    # ihn still, siehe seed.py).
    auth_seed_user1_username: str = "change-me"
    auth_seed_user1_password: str = "change-me"
    auth_seed_user2_username: str = "change-me-2"
    auth_seed_user2_password: str = "change-me"

    # Storage-Backend fuer das Login-Rate-Limiting (slowapi). Leer = redis_url wird
    # wiederverwendet (Produktion, siehe decisions/0005-auth-implementation.md - "kein neuer
    # Infrastruktur-Baustein"). Nur zu Testzwecken auf z.B. "memory://" ueberschreibbar, damit
    # die Testsuite ohne echtes Redis auskommt (siehe architecture/0002-testkonzept.md).
    rate_limit_storage_uri: str = ""

    def resolved_rate_limit_storage_uri(self) -> str:
        return self.rate_limit_storage_uri or self.redis_url

    # Erlaubte Frontend-Origins fuer CORS (specs/features/0005-minimal-project-frontend.md,
    # architecture/0003-securitykonzept.md) - komma-getrennt, kein Wildcard "*". Defaults decken
    # lokale Entwicklung ab (Vite-Dev-Server auf 5173, das ueber docker-compose gebaute
    # nginx-Frontend auf FRONTEND_PORT-Default 8080); in Produktion ueber CORS_ALLOWED_ORIGINS
    # auf die tatsaechliche(n) Frontend-Origin(s) setzen.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:8080"

    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Feature-Flag fuer die lokale Top-Foto-Auswahl mit Kategorie-Mix
    # (specs/features/0024-top-photo-selection-category-mix.md). Default AN (anders als ein
    # Cloud-Feature): rein lokale/kostenlose Verarbeitung, kein Grund fuer einen restriktiven
    # Default.
    category_selection_enabled: bool = True

    # Obergrenze fuer die begrenzte Parallelisierung von Download + Thumbnail-Erzeugung in Phase 2b
    # des Scans (specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020). Echter
    # Betriebsparameter (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud), deshalb ein
    # env-ueberschreibbares Settings-Feld statt einer reinen Modul-Konstante wie
    # worker.py::SCAN_COMMIT_BATCH_SIZE (das ist reiner Test-Kalibrierungswert). Default 4:
    # spuerbare Parallelisierung gegenueber dem bisherigen strikt seriellen Ablauf, ohne den Server
    # mit Dutzenden gleichzeitigen Downloads zu fluten. `Field(ge=1)` (test-engineer-/security-
    # engineer-Review-Fund): faellt bei einer fehlerhaften .env-Konfiguration (0/negativ) bereits
    # beim Prozessstart auf, statt sich erst mitten im naechsten Scan-Lauf als range(step=0)-Crash
    # zu aeussern - worker.py verlaesst sich seitdem direkt auf diesen validierten Wert, ohne
    # eigenen Laufzeit-Clamp.
    scan_download_concurrency: int = Field(default=4, ge=1)


settings = Settings()
