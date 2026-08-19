import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH 2026 Hackathon API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://sih-2026.pages.dev"
    ]
    
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "sih@gtmcnanded.in")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "SihGtmc2026!")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sih-2026-super-secret-jwt-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sih_2026.db")

    # Cloudflare D1 Credentials (Loaded from .env)
    CLOUDFLARE_ACCOUNT_ID: str = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    CLOUDFLARE_D1_DATABASE_ID: str = os.getenv("CLOUDFLARE_D1_DATABASE_ID", "")
    CLOUDFLARE_API_TOKEN: str = os.getenv("CLOUDFLARE_API_TOKEN", "")

    # Cloudflare R2 Credentials (Loaded from .env)
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET: str = os.getenv("R2_BUCKET", "sih-2026")
    R2_PUBLIC_DOMAIN: str = os.getenv("R2_PUBLIC_DOMAIN", "https://pub-013ef3ae7ba54fd696dc2bfd89477d38.r2.dev")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
