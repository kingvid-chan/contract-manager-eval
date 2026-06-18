"""Application configuration from environment variables."""

import os


class Settings:
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production-use-random-string")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "8"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/contract_manager.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))
    BASE_PATH: str = os.getenv("BASE_PATH", "/projects/contract-manager-eval")


settings = Settings()
