from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "NETRA"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    FRONTEND_URL: str = ""  # Deployed frontend URL (e.g., https://netra.vercel.app)

    # Database
    DATABASE_URL: str = ""  # Neon PostgreSQL connection string

    # AI Models - Primary
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_LITE_MODEL: str = "gemini-2.0-flash-lite"

    # AI Models - Fallback
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FAST_MODEL: str = "llama-3.1-8b-instant"

    # AI Model routing
    PRIMARY_TIMEOUT_MS: int = 15000
    FALLBACK_TIMEOUT_MS: int = 8000
    MAX_RETRIES: int = 2

    # Simulation
    SIMULATION_MAX_TURNS: int = 15
    INTERVENTION_CONFIDENCE_THRESHOLD: float = 0.85

    # Mapbox (for frontend, served via API for security)
    MAPBOX_TOKEN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
