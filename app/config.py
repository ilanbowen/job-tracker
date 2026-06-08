from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Job Tracker"
    app_env: str = "local"

    # Default is PostgreSQL, not SQLite. Kubernetes overrides this with the
    # DATABASE_URL generated in the Helm Secret.
    database_url: str = "postgresql+psycopg2://jobtracker:change-me-local-only@localhost:5432/jobtracker"
    # Uploaded logos are stored outside the container image.
    # In Kubernetes this path is backed by a PVC.
    logo_dir: str = "data/logos"
    # Optional fallback directory for logos bundled with the source tree/image.
    seed_logo_dir: str = "logos"
    # Internal service URL for LinkedIn company lookup. In Kubernetes this is
    # set to the linkedin-lookup Service by the Helm ConfigMap.
    linkedin_lookup_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
