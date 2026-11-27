from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV) if ROOT_ENV.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Order-to-Audit System"
    APP_ENV: str = "development"
    SECRET_KEY: str = "order-to-audit-nit-trichy-dev-secret-change-in-production-2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/order_to_audit"
    TEST_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/order_to_audit_test"

    FACTORY_NAME: str = "Kaveri Crunch Foods Pvt. Ltd."
    FACTORY_ADDRESS: str = "Plot 14, SIDCO Industrial Estate, Thuvakudi, Tiruchirappalli, Tamil Nadu - 620015"
    FACTORY_GSTIN: str = "33AABCK4821M1Z7"
    FACTORY_STATE: str = "Tamil Nadu"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:80,http://localhost"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
