#!/usr/bin/env python3

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Database Configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    # External Service APIs
    VAPI_API_KEY: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    RETELL_API_KEY: Optional[str] = None
    RETELL_AGENT_ID: Optional[str] = None
    BREVO_API_KEY: Optional[str] = None
    SENDER_EMAIL: str = "noreply@reachmagnets.com"
    SENDER_NAME: str = "Reach Magnets"
    WHATSAPP_API_URL: Optional[str] = None
    WHATSAPP_TOKEN: Optional[str] = None

    # New Retell Sarah Integration Settings
    OPENAI_API_KEY: Optional[str] = None
    CALCOM_API_KEY: Optional[str] = None
    CALCOM_EVENT_TYPE_ID: Optional[str] = None
    GMEET_LINK: Optional[str] = None
    EVOLUTION_API_URL: Optional[str] = None
    EVOLUTION_API_KEY: Optional[str] = None
    EVOLUTION_INSTANCE: Optional[str] = None
    BASE_URL: Optional[str] = None
    SECRET_KEY: Optional[str] = None
    RETELL_LLM_ID: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # SMTP and LinkedIn settings
    EMAIL_PROVIDER: str = "smtp"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    BYPASS_TIME_GATING: bool = False
    
    # IMAP Config
    IMAP_SERVER: Optional[str] = None
    IMAP_USER: Optional[str] = None
    IMAP_PASSWORD: Optional[str] = None

    LINKEDIN_SESSION_COOKIE: Optional[str] = None
    LINKEDIN_DAILY_LIMIT: int = 100

    # Application URLs
    FRONTEND_URL: str = "http://localhost:3000"

    # Redis Configuration for Rate Limiting and Caching
    REDIS_URL: str = "redis://localhost:6379"

    # Rate Limiting Configuration
    RATE_LIMIT_PER_MINUTE: int = 60
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 1000

    # Retry and Timeout Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 1
    TIMEOUT_SECONDS: int = 30

    # Security Configuration
    WEBHOOK_SECRET: str = ""
    REQUIRE_WEBHOOK_SIGNATURE: bool = False
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Environment Configuration
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SIMULATE_CALLS: bool = True

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # Database Pool Configuration
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_CONNECT_TIMEOUT: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"

    def validate_required_settings(self) -> dict:
        """Validate required settings and return status"""
        import warnings
        missing = []
        status = {"valid": True, "missing": []}

        # External services are optional but warned about
        if not self.VAPI_API_KEY:
            warnings.warn("VAPI_API_KEY not configured - Vapi integration disabled")
        if not self.TWILIO_PHONE_NUMBER:
            warnings.warn("TWILIO_PHONE_NUMBER not configured")

        if missing:
            status["valid"] = False
            status["missing"] = missing

        return status

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance for performance"""
    try:
        return Settings()
    except Exception as e:
        print(f"Warning: Settings loading error - {e}")
        # Return defaults
        return Settings(_env_file=None)

# Use this function everywhere instead of direct import
def get_settings_lazy() -> Settings:
    """Get settings with lazy initialization"""
    try:
        return get_settings()
    except Exception as e:
        print(f"Warning: Settings loading error - {e}")
        return Settings(_env_file=None)
