"""Runtime configuration for the composite building explorer API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    cache_dir: Path
    default_state: str
    cors_origins: list[str]

    @staticmethod
    def from_env() -> Settings:
        origins = os.getenv("BUILDSTOCK_API_CORS_ORIGINS", "http://localhost:4200")
        return Settings(
            cache_dir=Path(os.getenv("BUILDSTOCK_API_CACHE_DIR", "datasets/api")).expanduser(),
            default_state=os.getenv("BUILDSTOCK_API_DEFAULT_STATE", "DE"),
            cors_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        )
