from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    ENVIRONMENT: str = "development"
    BASE_DOMAIN: str = "atgo.local"

    DATABASE_URL: str = "postgresql+asyncpg://atgo:atgo_dev_password@postgres:5432/atgo"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    REDIS_URL: str = "redis://:atgo_redis_dev@redis:6379/0"

    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 60
    JWT_REFRESH_TTL_DAYS: int = 30

    CORS_ORIGINS: str = "http://localhost:3000,http://atgo.local"

    PADDLE_VENDOR_ID: str = ""
    PADDLE_API_KEY: str = ""
    PADDLE_PUBLIC_KEY: str = ""

    VNPAY_TMN_CODE: str = ""
    VNPAY_HASH_SECRET: str = ""

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    SENTRY_DSN: str = ""

    # Dynadot — optional. Leave DYNADOT_API_KEY empty to disable.
    DYNADOT_API_KEY: str = ""
    DYNADOT_PARENT_DOMAIN: str = ""        # defaults to BASE_DOMAIN
    PUBLIC_IPV4: str = ""                  # public IP this ATGO instance answers on

    # Cloudflare — recommended for production wildcard DNS / On-Demand TLS
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ZONE_ID: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
