from typing import Literal

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

    # Feature-Flag fuer die lokale Kriterien-Bewertung + Kategorie-Kuratierung
    # (urspruenglich specs/features/0024-top-photo-selection-category-mix.md, seit
    # specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md bewusst unter demselben
    # Namen weiterverwendet fuer POST /score-criteria - keine funktionale Aenderung des Flags
    # selbst, nur ein neuer Endpunkt dahinter). Default AN (anders als ein Cloud-Feature): rein
    # lokale/kostenlose Verarbeitung, kein Grund fuer einen restriktiven Default.
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

    # Obergrenze fuer die begrenzte Parallelisierung der pro-Unterordner-Bilddatei-Zaehlung im
    # Ordner-Browser (specs/features/0050-dateianzahl-im-ordner-browser.md, ADR
    # decisions/0028-ordner-browser-bilddatei-zaehlung.md). Echter Betriebsparameter
    # (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud bei parallelen
    # Zaehl-Traversierungen mehrerer Unterordner), deshalb analog scan_download_concurrency ein
    # env-ueberschreibbares Settings-Feld statt einer reinen Modul-Konstante wie
    # api/opencloud.py::FOLDER_COUNT_LIMIT (das ist reiner Anzeige-/UX-Wert ohne Tuning-Bedarf).
    # Default 4, `Field(ge=1)` faellt bei fehlerhafter .env-Konfiguration bereits beim
    # Prozessstart auf statt sich erst als Semaphore(0)-Deadlock zu aeussern.
    opencloud_folder_count_concurrency: int = Field(default=4, ge=1)

    # Erste tatsaechlich produktive Cloud-Abhaengigkeit im Kriterien-Scoring-Pfad
    # (specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-
    # landmark-erkennung.md) - exakt das opencloud_app_token-Muster (Secret nur ueber Env-Variable,
    # nie eingecheckt), kein Format-Check. Der ".env.example"-Platzhalter existierte bereits (aus
    # einem nie umgesetzten frueheren Cloud-Entwurf, ADR-0015-Kontext), war aber nie in Settings
    # verdrahtet - wird jetzt fuer einen echten, neuen Zweck reaktiviert.
    anthropic_api_key: str = ""

    # Obergrenze fuer die begrenzte Parallelisierung der Anthropic-Vision-Aufrufe in
    # run_criterion_scoring (ADR 0025 Punkt 3) - bewusst deutlich konservativer als
    # scan_download_concurrency (Default 4): reales Geld pro Anfrage und ein fremdes Rate-Limit,
    # nicht nur ein selbst betriebener OpenCloud-Server. `Field(ge=1)` faellt bei einer
    # fehlerhaften .env-Konfiguration bereits beim Prozessstart auf, analog den beiden
    # Concurrency-Feldern oben.
    landmark_api_concurrency: int = Field(default=2, ge=1)

    # Zweite, waehlbare Cloud-Provider-Option fuer das landmark-Kriterium
    # (specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-
    # provider-option-cloud-landmark.md Punkt 3) - reine Betreiber-/Deployment-Entscheidung, kein
    # Project-Feld/Runtime-Selektor. `Literal` statt Enum (Minimalismus-Prinzip ADR 0006,
    # analog scan_download_concurrency-Field(ge=1) oben): pydantic validiert einen nicht
    # unterstuetzten .env-Wert bereits beim Prozessstart (ValidationError), kein stiller Fallback.
    landmark_provider: Literal["anthropic", "mistral"] = "anthropic"

    # Exakt das anthropic_api_key-Muster (Secret nur ueber Env-Variable, nie eingecheckt, kein
    # Format-Check) - nur ausgelesen, wenn landmark_provider == "mistral".
    mistral_api_key: str = ""


settings = Settings()
