from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from photosort.cloud_vision import (
    DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER,
    VISION_MODELS_BY_PROVIDER,
    default_vision_model_for_provider,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://photosort:photosort@localhost:5432/photosort"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    opencloud_base_url: str = ""
    opencloud_username: str = ""
    opencloud_app_token: str = ""
    opencloud_drive_name: str = ""

    # Lokaler Verarbeitungs-Cache für Thumbnails, über das "photo_cache"-Docker-Volume auf
    # backend und worker gemountet (docker-compose.yml).
    photo_cache_dir: str = "/data/photo-cache"

    # Initiale Benutzerkonten für die Seed-Migration. Die Usernamen-Platzhalter sind bewusst
    # unterschiedlich: identische Defaults würden bei unverändertem .env dazu führen, dass die
    # idempotente Seed-Migration nur EINEN statt zwei Accounts anlegt - seed_user() findet den
    # zweiten Username bereits vor und überspringt ihn still (seed.py).
    auth_seed_user1_username: str = "change-me"
    auth_seed_user1_password: str = "change-me"
    auth_seed_user2_username: str = "change-me-2"
    auth_seed_user2_password: str = "change-me"

    # Storage-Backend für das Login-Rate-Limiting (slowapi). Leer = redis_url wird
    # wiederverwendet - kein eigener Infrastruktur-Baustein. Nur zu Testzwecken auf z.B.
    # "memory://" überschreibbar, damit die Testsuite ohne echtes Redis auskommt.
    rate_limit_storage_uri: str = ""

    def resolved_rate_limit_storage_uri(self) -> str:
        return self.rate_limit_storage_uri or self.redis_url

    # Erlaubte Frontend-Origins für CORS - komma-getrennt, kein Wildcard "*". Defaults decken
    # lokale Entwicklung ab (Vite-Dev-Server auf 5173, das über docker-compose gebaute
    # nginx-Frontend auf FRONTEND_PORT-Default 8080); in Produktion über CORS_ALLOWED_ORIGINS auf
    # die tatsächliche(n) Frontend-Origin(s) setzen.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:8080"

    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Feature-Flag für die lokale Kriterien-Bewertung + Kategorie-Kuratierung; es deckt trotz
    # seines Namens auch POST /classify ab. Default AN (anders als bei einem Cloud-Feature): rein
    # lokale, kostenlose Verarbeitung, kein Grund für einen restriktiven Default.
    category_selection_enabled: bool = True

    # Obergrenze für die begrenzte Parallelisierung von Download + Thumbnail-Erzeugung in Phase
    # 2b des Scans. Echter Betriebsparameter (Überlastschutz für den
    # Einzelnutzer-Homeserver-OpenCloud), deshalb ein env-überschreibbares Settings-Feld statt
    # einer reinen Modul-Konstante wie worker.py::SCAN_COMMIT_BATCH_SIZE (reiner
    # Test-Kalibrierungswert). `Field(ge=1)`: eine fehlerhafte .env-Konfiguration (0/negativ)
    # fällt bereits beim Prozessstart auf, statt sich erst mitten im nächsten Scan-Lauf als
    # range(step=0)-Crash zu äußern - worker.py verlässt sich direkt auf diesen validierten Wert,
    # ohne eigenen Laufzeit-Clamp.
    scan_download_concurrency: int = Field(default=4, ge=1)

    # Obergrenze für die begrenzte Parallelisierung der pro-Unterordner-Bilddatei-Zählung im
    # Ordner-Browser. Echter Betriebsparameter wie scan_download_concurrency oben, deshalb
    # ebenfalls ein Settings-Feld statt einer Modul-Konstante wie
    # api/opencloud.py::FOLDER_COUNT_LIMIT (reiner Anzeige-/UX-Wert ohne Tuning-Bedarf).
    # `Field(ge=1)` fällt beim Prozessstart auf, statt sich als Semaphore(0)-Deadlock zu äußern.
    opencloud_folder_count_concurrency: int = Field(default=4, ge=1)

    # Exakt das opencloud_app_token-Muster: Secret nur über Env-Variable, nie eingecheckt, kein
    # Format-Check.
    anthropic_api_key: str = ""

    # Obergrenze für die begrenzte Parallelisierung der Cloud-Vision-Aufrufe in
    # run_criterion_scoring - bewusst deutlich konservativer als scan_download_concurrency:
    # reales Geld pro Anfrage und ein fremdes Rate-Limit, nicht nur ein selbst betriebener
    # OpenCloud-Server. `Field(ge=1)` wie bei den Concurrency-Feldern oben.
    landmark_api_concurrency: int = Field(default=2, ge=1)

    # Wählbare Cloud-Provider-Option - reine Betreiber-/Deployment-Entscheidung, kein
    # Project-Feld und kein Runtime-Selektor. `Literal` statt Enum: pydantic validiert einen
    # nicht unterstützten .env-Wert bereits beim Prozessstart (ValidationError), kein stiller
    # Fallback.
    landmark_provider: Literal["anthropic", "mistral"] = "anthropic"

    # Die zweite Betriebseinstellung neben der Anbieterwahl - WELCHES Modell des eingestellten
    # Anbieters benutzt wird. Leer heißt "Voreinstellung des eingestellten Anbieters" (erstes
    # Element seiner Registry), NICHT "kein Modell".
    #
    # Der Name erbt bewusst die Ungenauigkeit von `landmark_provider` daneben: beide gelten für
    # BEIDE Cloud-Anteile - Sehenswürdigkeits-Erkennung UND Kategorie-Vorschläge, nicht nur für
    # landmark. Die Zusammengehörigkeit des Schalterpaars `LANDMARK_PROVIDER`/`LANDMARK_MODEL`
    # wiegt schwerer als die Wortgenauigkeit, und ein Umbenennen wäre für den Betrieb breaking.
    #
    # `str` + Validator statt `Literal`, anders als bei landmark_provider: die zulässigen Werte
    # hängen vom eingestellten Anbieter ab, das lässt sich in einem Feld-`Literal` nicht
    # ausdrücken. Die Startvalidierung unten liefert dafür dieselbe Zusicherung.
    landmark_model: str = ""

    def resolved_landmark_model(self) -> str:
        """Das tatsächlich zu verwendende Modell (Muster `resolved_rate_limit_storage_uri()`).

        EINMAL je Cloud-Phase aufzurufen und der Wert dann durchzureichen: Client-Bau,
        Kostenrechnung und Modellspalte des Laufs müssen strukturell denselben Wert benutzen,
        nicht drei zufällig übereinstimmende Lesevorgänge derselben globalen `settings`."""
        return self.landmark_model or default_vision_model_for_provider(self.landmark_provider)

    @field_validator("landmark_model")
    @classmethod
    def _check_landmark_model_is_offered_by_the_provider(
        cls, value: str, info: ValidationInfo
    ) -> str:
        """Ein Wert außerhalb der gepflegten Auswahl führt zu einer verständlichen Fehlermeldung
        BEIM START; die Anwendung startet dann nicht, statt mitten in einem laufenden -
        kostenpflichtigen - Durchgang still fehlzuschlagen. Wegen `settings = Settings()` auf
        Modulebene ist das der Prozessstart.

        Geprüft wird gegen die Registry DES EINGESTELLTEN ANBIETERS: ein für Anthropic gültiges
        Modell unter `mistral` ist ebenfalls ein Startfehler - sonst wäre es ein Aufruf, den der
        Anbieter erst zur Laufzeit ablehnt, mitten im kostenpflichtigen Durchgang.

        FELD-VALIDATOR, NICHT `model_validator(mode="after")`: pydantic hängt an eine
        `ValidationError` die Eingabe an, an der die Prüfung scheiterte - bei einem
        Modell-Validator wäre das das VOLLSTÄNDIGE Settings-Dict, und damit ständen `SECRET_KEY`,
        beide Cloud-API-Keys und `OPENCLOUD_APP_TOKEN` im Startup-Traceback (`docker compose
        logs`) und in `exc.errors()`/`exc.json()`. Abgesichert durch
        `test_config.py::test_the_rejection_leaks_no_other_settings_value`.

        `landmark_model` ist hinter `landmark_provider` deklariert, deshalb steht der Anbieter in
        `info.data`. Fehlt er dort, ist er selbst ungültig - dann bricht der Start ohnehin an
        seinem eigenen Feldfehler ab, und eine zweite Meldung hier hilft niemandem."""
        if not value:
            return value
        provider = info.data.get("landmark_provider")
        if provider is None:
            return value
        allowed = VISION_MODELS_BY_PROVIDER.get(provider, ())
        if value not in allowed:
            # Bewusst enthalten: der beanstandete Wert, der eingestellte Anbieter und die
            # zulässigen Werte - Modell-IDs sind keine Geheimnisse (die Registry liegt im
            # öffentlichen Repository), und der Betreiber soll handlungsfähig sein.
            raise ValueError(
                f"LANDMARK_MODEL={value!r} ist fuer LANDMARK_PROVIDER={provider!r} nicht "
                f"waehlbar. Erlaubt sind: {', '.join(allowed)} (oder leer lassen fuer die "
                f"Voreinstellung {default_vision_model_for_provider(provider)})."
            )
        return value

    # Exakt das anthropic_api_key-Muster (Secret nur über Env-Variable, nie eingecheckt, kein
    # Format-Check) - der Wert wird wie jedes andere Settings-Feld beim Prozessstart eingelesen,
    # aber nur verwendet (build_landmark_client()), wenn landmark_provider == "mistral".
    mistral_api_key: str = ""

    # Obergrenze für die begrenzte Parallelisierung der Cloud-Aufrufe der
    # Remote-Kategorie-Klassifizierung - analog landmark_api_concurrency. Bewusst ein eigenes
    # Setting statt dessen Wiederverwendung: ein eigenständiger Job mit eigener Kandidatenmenge
    # (kompletter Ausschuss-Bestand statt eines Vorfilter-Ergebnisses) soll unabhängig davon
    # tunbar bleiben.
    remote_category_classification_concurrency: int = Field(default=2, ge=1)

    # Die ANFRAGERATE an den Anbieter, für BEIDE Cloud-Teilschritte gemeinsam. Sie muss ein
    # Settings-Feld sein und darf keine Modulkonstante wie VISION_REQUEST_TIMEOUT_SECONDS werden:
    # die zulässige Rate hängt an der KONTOSTUFE des Betreibers, ist also ein Betriebsparameter.
    # Versuchszahl, Wartebudget, Staffel und Deckel bleiben aus demselben Grund Modulkonstanten
    # in cloud_vision.py - sie hängen an der Watchdog-Rechnung, nicht an einer Kontostufe.
    #
    # `0` heißt "Voreinstellung des eingestellten Anbieters" (Muster von `LANDMARK_MODEL`).
    # ACHTUNG, UNTERSCHIED ZU `LANDMARK_MODEL=`: ein LEERER Wert ist für ein Zahlenfeld ein
    # Startfehler, kein "nicht gesetzt" - `.env.example` trägt deshalb `=0` und sagt das
    # ausdrücklich. `ge=0` analog den Concurrency-Feldern oben: eine fehlerhafte .env fällt beim
    # Prozessstart auf, nicht mitten im nächsten kostenpflichtigen Lauf.
    cloud_vision_requests_per_minute: int = Field(default=0, ge=0)

    def resolved_cloud_vision_requests_per_minute(self, provider: str) -> int:
        """Die tatsächlich zu verwendende Anfragerate (Muster `resolved_landmark_model()`).

        Gibt NIEMALS `0` zurück: aus dem Rückgabewert bildet cloud_vision_throttle.py zur
        MODUL-IMPORTZEIT den Mindestabstand `60 / rate`. Eine `0` von hier wäre ein
        ZeroDivisionError beim Import - und damit ein gleichzeitiger Startfehler von Backend UND
        Worker statt eines fehlgeschlagenen Laufs. Getragen wird das von zwei Seiten: `ge=0`
        schließt negative Werte aus, und die Voreinstellungstabelle enthält (per Test erzwungen)
        für jeden wählbaren Anbieter einen Wert > 0."""
        return (
            self.cloud_vision_requests_per_minute
            or DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER[provider]
        )


settings = Settings()
