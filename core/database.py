"""
Database connection and session management for SQLAlchemy.
Supports both PostgreSQL (Supabase) and local SQLite with automated table initialization.
"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from core.config import settings

logger = logging.getLogger("JP001.Database")

# Prepare engine arguments depending on dialect
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and seed initial categorization rules."""
    from core import models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created successfully.")

    # Seed default categorization rules if table is empty
    db = SessionLocal()
    try:
        rule_count = db.query(models.CategorizationRule).count()
        if rule_count == 0:
            logger.info("Seeding initial categorization rules...")
            default_rules = [
                models.CategorizationRule(
                    name="Development Tools & SDKs",
                    priority=10,
                    enabled=True,
                    category="Development",
                    conditions={
                        "extensions": [".py", ".pyw", ".ipynb", ".java", ".c", ".cpp", ".cs", ".rs", ".go", ".js", ".ts", ".sh", ".json", ".yaml", ".sql"],
                        "keywords": ["code", "dev", "sdk", "compiler", "python", "node", "git", "cargo", "docker", "npm", "pip", "debug", "api", "ide"],
                        "path_patterns": ["*/src/*", "*/source/*", "*/dev/*", "*/build/*", "*/node_modules/*", "*/venv/*", "*/bin/*"]
                    }
                ),
                models.CategorizationRule(
                    name="Media & Graphics",
                    priority=20,
                    enabled=True,
                    category="Media & Graphics",
                    conditions={
                        "extensions": [".mp4", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".blend", ".fbx"],
                        "keywords": ["media", "audio", "video", "music", "image", "photo", "vlc", "ffmpeg", "blender", "photoshop", "gimp", "player"],
                        "path_patterns": ["*/media/*", "*/music/*", "*/video/*", "*/pictures/*", "*/images/*"]
                    }
                ),
                models.CategorizationRule(
                    name="Games & Entertainment",
                    priority=30,
                    enabled=True,
                    category="Games & Entertainment",
                    conditions={
                        "extensions": [".rom", ".nes", ".gba", ".nds", ".unity3d", ".pak", ".wad", ".sav"],
                        "keywords": ["game", "steam", "epic", "unity", "unreal", "play", "arcade", "rpg", "emulator", "retro", "minecraft"],
                        "path_patterns": ["*/games/*", "*/steamapps/*", "*/emulators/*", "*/roms/*"]
                    }
                ),
                models.CategorizationRule(
                    name="Documents & Productivity",
                    priority=40,
                    enabled=True,
                    category="Documents & Productivity",
                    conditions={
                        "extensions": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".csv", ".tsv", ".md"],
                        "keywords": ["doc", "document", "sheet", "presentation", "report", "office", "word", "excel", "powerpoint", "notes", "manual"],
                        "path_patterns": ["*/documents/*", "*/docs/*", "*/reports/*", "*/notes/*"]
                    }
                ),
                models.CategorizationRule(
                    name="Utilities & Tools",
                    priority=50,
                    enabled=True,
                    category="Utilities & Tools",
                    conditions={
                        "extensions": [".exe", ".msi", ".dmg", ".pkg", ".appimage", ".deb", ".rpm", ".zip", ".tar", ".gz", ".7z", ".dll", ".so", ".ini", ".cfg", ".sys"],
                        "keywords": ["util", "utility", "tool", "installer", "setup", "patch", "driver", "cleaner", "monitor", "terminal", "sysinternals", "registry", "service"],
                        "path_patterns": ["*/tools/*", "*/utils/*", "*/utilities/*", "*/drivers/*", "*/installer/*", "*/downloads/*"]
                    }
                )
            ]
            db.add_all(default_rules)
            db.commit()
            logger.info("Successfully seeded %d initial categorization rules.", len(default_rules))
    except Exception as err:
        logger.error("Error during database initialization: %s", err)
        db.rollback()
    finally:
        db.close()
