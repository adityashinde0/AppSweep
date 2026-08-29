"""
Configuration settings and environment management for JP-001.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union


class Settings:
    """Application configuration settings."""

    def __init__(self) -> None:
        self.app_name: str = "JP-001 Duplicate Application Manager"
        self.app_version: str = "1.0.0"
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

        # Database Configuration
        # Defaults to local SQLite file database with zero-setup if DATABASE_URL or SUPABASE_URL not provided
        self.database_url: str = (
            os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DATABASE_URL")
            or os.getenv("SUPABASE_URL")
            or f"sqlite:///{Path('./jp001_local.db').resolve().as_posix()}"
        )

        # Quarantine Storage Directory
        quarantine_env = os.getenv("QUARANTINE_DIR", "./.quarantine")
        self.quarantine_dir: Path = Path(quarantine_env).resolve()
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

        # Streaming Chunk Buffer (Default: 64 KB)
        self.chunk_size: int = int(os.getenv("CHUNK_SIZE", str(64 * 1024)))

        # Allowed Roots for Scan / Removal Guardrails
        raw_allowed = os.getenv("ALLOWED_ROOTS", "")
        self.allowed_roots: List[Path] = [
            Path(r.strip()).resolve() for r in raw_allowed.split(";") if r.strip()
        ]

    def is_path_allowed(self, path: Union[str, Path]) -> bool:
        """Check if a path is permitted under configured allowed roots."""
        if not self.allowed_roots:
            return True  # If not configured, allow local paths
        resolved_path = Path(path).resolve()
        for root in self.allowed_roots:
            try:
                resolved_path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def sanitize_path(self, path: Union[str, Path]) -> Path:
        """Resolve and validate path against traversal attacks."""
        resolved = Path(path).resolve()
        # Ensure no null bytes or illegal characters
        if "\0" in str(resolved):
            raise ValueError("Path contains invalid null byte")
        return resolved


settings = Settings()
