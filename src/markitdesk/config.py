import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    # Workspace and output directories
    workspace_root: Path = Field(
        default=Path("./workspace"),
        description="Root directory for allowed file access",
    )
    output_root: Path = Field(
        default=Path("./output"),
        description="Root directory for conversion output",
    )

    # Security and feature flags
    max_file_mb: int = Field(
        default=100,
        description="Maximum file size in megabytes allowed for processing",
    )
    allow_plugins: bool = Field(
        default=False,
        description="Enable plugin system (security boundary)",
    )
    allow_remote_urls: bool = Field(
        default=False,
        description="Allow processing of remote URLs (requires network)",
    )
    allow_ai_enrichment: bool = Field(
        default=False,
        description="Enable AI enrichment features (keeps raw output separate)",
    )
    # ZIP handling configuration
    allow_zip_extract: bool = Field(
        default=True,
        description="Allow extraction and processing of ZIP archives",
    )
    max_zip_files: int = Field(
        default=500,
        description="Maximum number of files allowed in a ZIP archive",
    )
    max_zip_uncompressed_mb: int = Field(
        default=500,
        description="Maximum uncompressed size in MB allowed for ZIP archives",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()