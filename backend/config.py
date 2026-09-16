"""
Centralized configuration management using Pydantic Settings.

Load from environment variables with validation and sensible defaults.
Usage:
    from backend.config import settings
    print(settings.database_url)
    print(settings.allowed_origins)
"""

import logging
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./aegisnet.db"
    
    # JWT & Security
    jwt_secret: str = "dev-only-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    demo_password: str = "changeme"
    
    # Redis
    redis_url: str | None = None
    
    # CORS - RESTRICTED by default (security first)
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:4173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
    ]
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 120
    
    # HTTPS/TLS
    enable_https: bool = False
    ssl_cert_file: str | None = None
    ssl_key_file: str | None = None
    
    # Logging
    log_level: str = "INFO"
    
    # Environment
    environment: str = "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"
    
    def validate_production(self) -> None:
        """Validate critical security settings for production."""
        if self.environment == "production":
            if self.jwt_secret == "dev-only-secret-change-in-production":
                raise ValueError(
                    "❌ PRODUCTION: JWT_SECRET must be changed from default. "
                    "Set AEGISNET_JWT_SECRET to a secure random value (min 32 chars)."
                )
            
            if "*" in self.allowed_origins:
                raise ValueError(
                    "❌ PRODUCTION: CORS wildcard '*' is insecure. "
                    "Set ALLOWED_ORIGINS to specific domains only."
                )
            
            if self.demo_password == "changeme":
                raise ValueError(
                    "❌ PRODUCTION: Demo password must be changed. "
                    "Set AEGISNET_DEMO_PASSWORD to a secure value."
                )
            
            if not self.enable_https and self.environment == "production":
                logging.warning(
                    "⚠️  PRODUCTION: ENABLE_HTTPS is False. "
                    "Use a reverse proxy (nginx/caddy) with TLS in production."
                )
    
    def get_log_level(self) -> int:
        """Convert log level string to logging constant."""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(self.log_level.upper(), logging.INFO)


# Global settings instance
settings = Settings()

# Validate on production startup
if settings.environment == "production":
    settings.validate_production()
