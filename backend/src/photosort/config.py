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


settings = Settings()
