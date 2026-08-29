#!/usr/bin/env python3
"""
Intelligent Application Management & Duplicate Detection Tool.

This module provides content-based duplicate application detection using SHA-256
cryptographic hashing with byte-size pre-filtering and 64 KB memory-buffered chunked
streaming, along with rule-based categorization, visual progress tracking, robust
Windows permission error resilience, and safe interactive deletion workflows.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# ============================================================================
# Constants & Defaults
# ============================================================================

DEFAULT_CHUNK_SIZE: int = 65536  # 64 KB buffer for memory-efficient hashing
DEFAULT_RULES_FILE: str = "rules.json"
DEFAULT_LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Built-in fallback rules if rules.json is missing or corrupted
FALLBACK_RULES: List[Dict[str, Any]] = [
    {
        "category": "Development",
        "description": "Programming languages, scripts, SDKs, IDEs, and developer tools",
        "extensions": [
            ".py", ".pyw", ".ipynb", ".java", ".c", ".cpp", ".h", ".hpp",
            ".cs", ".rs", ".go", ".js", ".mjs", ".cjs", ".ts", ".tsx",
            ".jsx", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".rb", ".php",
            ".swift", ".kt", ".gradle", ".json", ".yaml", ".yml", ".toml",
            ".xml", ".sql"
        ],
        "keywords": [
            "code", "coding", "dev", "developer", "development", "vscode", "sdk",
            "compiler", "node", "python", "git", "cargo", "maven", "gradle",
            "docker", "npm", "yarn", "pip", "debug", "debugger", "server", "api",
            "ide", "interpreter", "build"
        ],
        "path_patterns": [
            "*/src/*", "*/source/*", "*/dev/*", "*/build/*", "*/node_modules/*",
            "*/venv/*", "*/env/*", "*/.git/*", "*/bin/*", "*/lib/*", "*/scripts/*"
        ]
    },
    {
        "category": "Media & Graphics",
        "description": "Audio, video, image, 3D modeling, and creative media files",
        "extensions": [
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
            ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
            ".psd", ".ai", ".blend", ".fbx", ".obj", ".3ds"
        ],
        "keywords": [
            "media", "audio", "video", "music", "sound", "photo", "image",
            "graphics", "vlc", "ffmpeg", "encoder", "decoder", "blender",
            "photoshop", "gimp", "player", "recorder", "render", "camera",
            "stream", "track"
        ],
        "path_patterns": [
            "*/media/*", "*/music/*", "*/video/*", "*/pictures/*", "*/images/*",
            "*/assets/*", "*/audio/*", "*/photos/*"
        ]
    },
    {
        "category": "Games & Entertainment",
        "description": "Game binaries, assets, emulators, and gaming launchers",
        "extensions": [
            ".rom", ".nes", ".sfc", ".gba", ".nds", ".unity3d", ".pak",
            ".wad", ".sav", ".gam"
        ],
        "keywords": [
            "game", "games", "gaming", "steam", "epic", "unity", "unreal",
            "play", "arcade", "rpg", "fps", "emulator", "retro", "minecraft",
            "roblox", "launcher", "quest"
        ],
        "path_patterns": [
            "*/games/*", "*/steamapps/*", "*/emulators/*", "*/roms/*", "*/game_saves/*"
        ]
    },
    {
        "category": "Documents & Productivity",
        "description": "Office documents, spreadsheets, presentations, and publications",
        "extensions": [
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
            ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".tsv",
            ".md", ".epub"
        ],
        "keywords": [
            "doc", "docs", "document", "documents", "sheet", "sheets", "calc",
            "presentation", "report", "reports", "invoice", "resume", "office",
            "word", "excel", "powerpoint", "notes", "manual", "guide", "paper",
            "summary", "contract"
        ],
        "path_patterns": [
            "*/documents/*", "*/docs/*", "*/reports/*", "*/sheets/*", "*/notes/*",
            "*/office/*", "*/papers/*"
        ]
    },
    {
        "category": "Utilities & Tools",
        "description": "Executables, installers, archives, drivers, and system maintenance utilities",
        "extensions": [
            ".exe", ".msi", ".dmg", ".pkg", ".appimage", ".deb", ".rpm",
            ".zip", ".tar", ".gz", ".7z", ".rar", ".iso", ".bin",
            ".dll", ".so", ".dylib", ".cfg", ".ini", ".log", ".sys"
        ],
        "keywords": [
            "util", "utility", "utilities", "tool", "tools", "installer",
            "setup", "patch", "driver", "drivers", "archiver", "zip",
            "backup", "cleaner", "monitor", "terminal", "powershell",
            "sysinternals", "registry", "service", "manager", "agent",
            "helper", "daemon", "updater"
        ],
        "path_patterns": [
            "*/tools/*", "*/utils/*", "*/utilities/*", "*/drivers/*", "*/installer/*",
            "*/downloads/*", "*/system/*", "*/bin/*", "*/setup/*"
        ]
    }
]


# ============================================================================
# Data Models
# ============================================================================

@dataclasses.dataclass
class Rule:
    """Represents a categorization rule loaded from configuration."""
    category: str
    description: str = ""
    extensions: List[str] = dataclasses.field(default_factory=list)
    keywords: List[str] = dataclasses.field(default_factory=list)
    path_patterns: List[str] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Rule:
        """Create a normalized Rule instance from raw dictionary."""
        category = str(data.get("category", "Uncategorized")).strip()
        description = str(data.get("description", "")).strip()

        # Normalize extensions (lowercase, ensure leading dot)
        raw_exts = data.get("extensions", [])
        extensions: List[str] = []
        for ext in raw_exts:
            clean_ext = str(ext).strip().lower()
            if clean_ext:
                if not clean_ext.startswith("."):
                    clean_ext = f".{clean_ext}"
                extensions.append(clean_ext)

        # Normalize keywords (lowercase)
        raw_keywords = data.get("keywords", [])
        keywords = [str(k).strip().lower() for k in raw_keywords if str(k).strip()]

        # Normalize path patterns (lowercase, forward slashes)
        raw_patterns = data.get("path_patterns", [])
        path_patterns = [str(p).strip().replace("\\", "/").lower() for p in raw_patterns if str(p).strip()]

        return cls(
            category=category,
            description=description,
            extensions=extensions,
            keywords=keywords,
            path_patterns=path_patterns,
        )


@dataclasses.dataclass
class FileRecord:
    """Encapsulates metadata and hash for a scanned file."""
    path: Path
    size: int
    category: str = "Uncategorized"
    sha256_hash: Optional[str] = None
    modified_time: float = 0.0

    @property
    def formatted_size(self) -> str:
        """Return human-readable file size."""
        return format_bytes(self.size)


# ============================================================================
# Utilities, Progress Bar & Path Helpers
# ============================================================================

def normalize_path(path: Union[str, Path]) -> Path:
    """
    Safely resolve a path to an absolute, normalized Path object across Windows and POSIX.
    Handles relative paths, redundant separators, and Windows long paths.
    """
    try:
        return Path(path).resolve()
    except (OSError, ValueError):
        return Path(os.path.abspath(str(path)))


def format_bytes(byte_count: int) -> str:
    """Convert an integer byte count into a human-readable string representation."""
    if byte_count < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(byte_count)
    unit_idx = 0
    while value >= 1024.0 and unit_idx < len(units) - 1:
        value /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(value)} {units[unit_idx]}"
    return f"{value:.2f} {units[unit_idx]}"


class ProgressBar:
    """
    Console progress indicator with dynamic width adjustment and TTY detection.
    Falls back to periodic milestone logging in non-interactive/redirected environments.
    """

    def __init__(
        self,
        total: int,
        prefix: str = "Progress",
        bar_length: int = 25,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.total = max(1, total)
        self.prefix = prefix
        self.bar_length = bar_length
        self.logger = logger
        self.is_tty = sys.stdout.isatty()
        self.current = 0
        self.last_log_percent = -1
        self.start_time = time.perf_counter()

    def update(self, current: int, item_name: str = "") -> None:
        """Update progress bar with current index and optional active item label."""
        self.current = min(current, self.total)
        percent = (self.current / self.total) * 100.0

        if self.is_tty:
            try:
                term_width = shutil.get_terminal_size((80, 20)).columns
            except OSError:
                term_width = 80

            filled = int(self.bar_length * self.current // self.total)
            bar = "█" * filled + "░" * (self.bar_length - filled)
            status_text = f"{self.prefix}: [{bar}] {percent:5.1f}% ({self.current}/{self.total})"

            if item_name:
                available_space = term_width - len(status_text) - 5
                if available_space > 8:
                    truncated_name = item_name if len(item_name) <= available_space else f"...{item_name[-(available_space - 3):]}"
                    status_text += f" | {truncated_name}"

            # Pad to clear residual characters and carriage return
            sys.stdout.write(f"\r{status_text.ljust(term_width - 1)}")
            sys.stdout.flush()
        else:
            # Periodic logging in non-TTY mode (every 20% or on completion)
            int_percent = int(percent // 20) * 20
            if int_percent != self.last_log_percent and self.logger:
                self.last_log_percent = int_percent
                self.logger.info(
                    "%s: %3.0f%% complete (%d/%d items processed)",
                    self.prefix, percent, self.current, self.total
                )

    def finish(self, message: str = "") -> None:
        """Complete the progress display and clean up terminal line."""
        if self.is_tty:
            sys.stdout.write("\r" + " " * (shutil.get_terminal_size((80, 20)).columns - 1) + "\r")
            if message:
                sys.stdout.write(f"[+] {message}\n")
            sys.stdout.flush()
        elif self.logger and message:
            self.logger.info("[+] %s", message)


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure and return the root application logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("AppManager")
    logger.setLevel(level)

    # Avoid duplicate handlers on re-initialization
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (if requested)
    if log_file:
        try:
            log_path = normalize_path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info("Logging configured to write to file: %s", log_path)
        except (OSError, PermissionError) as err:
            logger.warning("Failed to configure file logging to '%s': %s", log_file, err)

    return logger


# ============================================================================
# Rule-Based Categorization Engine
# ============================================================================

class RuleEngine:
    """Evaluates files against configurable categorization rules."""

    def __init__(
        self,
        rules_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None
    ) -> None:
        self.logger = logger or logging.getLogger("AppManager.RuleEngine")
        self.rules: List[Rule] = []
        if rules_path:
            self.load_rules(rules_path)
        else:
            self._load_fallback_rules()

    def _load_fallback_rules(self) -> None:
        """Load built-in default rules as fallback."""
        self.rules = [Rule.from_dict(r) for r in FALLBACK_RULES]
        self.logger.info("Loaded %d built-in fallback categorization rules.", len(self.rules))

    def load_rules(self, rules_path: Union[str, Path]) -> None:
        """
        Load categorization rules from an external JSON file.
        Falls back to built-in rules if file cannot be read or decoded.
        """
        path = normalize_path(rules_path)
        if not path.exists():
            self.logger.warning("Rules configuration file '%s' not found. Falling back to built-in rules.", path)
            self._load_fallback_rules()
            return

        if not path.is_file():
            self.logger.warning("Rules path '%s' is not a regular file. Falling back to built-in rules.", path)
            self._load_fallback_rules()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    self.logger.warning("Rules file '%s' is empty. Falling back to built-in rules.", path)
                    self._load_fallback_rules()
                    return
                data = json.loads(content)

            raw_rules = data.get("rules", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if not raw_rules:
                self.logger.warning("No rule definitions found in '%s'. Falling back to built-in rules.", path)
                self._load_fallback_rules()
                return

            self.rules = [Rule.from_dict(r) for r in raw_rules]
            self.logger.info("Successfully loaded %d categorization rules from '%s'.", len(self.rules), path)
        except json.JSONDecodeError as err:
            self.logger.error("JSON syntax error in rules file '%s': %s. Falling back to built-in rules.", path, err)
            self._load_fallback_rules()
        except (PermissionError, OSError) as err:
            self.logger.error("Failed to read rules file '%s': %s. Falling back to built-in rules.", path, err)
            self._load_fallback_rules()

    @staticmethod
    def _matches_keyword(keyword: str, text: str) -> bool:
        """
        Check if a keyword matches as a distinct token or delimited word in text.
        Prevents false substring positives (e.g. 'code' matching inside 'encoder').
        """
        kw = keyword.strip().lower()
        if not kw:
            return False
        # Check delimited boundary or exact match
        pattern = rf"(?:^|[\W_]){re.escape(kw)}(?:$|[\W_])"
        if re.search(pattern, text, re.IGNORECASE):
            return True
        # For longer keywords (>= 6 chars), allow prefix/suffix match (e.g. 'installer' in 'myappinstaller')
        if len(kw) >= 6 and (text.lower().startswith(kw) or text.lower().endswith(kw)):
            return True
        return False

    def categorize(self, file_path: Union[str, Path]) -> str:
        """
        Evaluate file metadata against active rules.
        Returns matching category name or 'Uncategorized' if no rules match.
        Normalizes Windows paths and drive letters for consistent pattern matching.
        """
        p = normalize_path(file_path)
        ext = p.suffix.lower()
        name_lower = p.name.lower()
        stem_lower = p.stem.lower()

        # Windows and POSIX path normalization
        full_path_norm = str(p).replace("\\", "/").lower()
        parent_dir_norm = str(p.parent).replace("\\", "/").lower()

        for rule in self.rules:
            # 1. Match File Extension
            if ext and ext in rule.extensions:
                self.logger.debug("File '%s' matched category '%s' via extension '%s'", p.name, rule.category, ext)
                return rule.category

            # 2. Match Keywords in filename / stem (boundary-aware)
            for kw in rule.keywords:
                if self._matches_keyword(kw, stem_lower) or self._matches_keyword(kw, name_lower):
                    self.logger.debug("File '%s' matched category '%s' via keyword '%s'", p.name, rule.category, kw)
                    return rule.category

            # 3. Match Path Patterns on normalized directory or full path
            for pattern in rule.path_patterns:
                pat = pattern.replace("\\", "/").lower()
                clean_core = pat.strip("*").strip("/")
                if (
                    fnmatch.fnmatch(parent_dir_norm, pat)
                    or (clean_core and clean_core in parent_dir_norm)
                    or fnmatch.fnmatch(full_path_norm, pat)
                ):
                    self.logger.debug("File '%s' matched category '%s' via path pattern '%s'", p.name, rule.category, pattern)
                    return rule.category

        self.logger.debug("File '%s' did not match any rule. Categorized as 'Uncategorized'.", p.name)
        return "Uncategorized"


# ============================================================================
# Main Engine: ApplicationManager
# ============================================================================

class ApplicationManager:
    """
    Core engine for content-based duplicate application detection,
    rule-based categorization, and safe file operations.
    """

    def __init__(
        self,
        rules_path: Optional[Union[str, Path]] = DEFAULT_RULES_FILE,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.chunk_size = max(1024, chunk_size)  # Min buffer size 1 KB, default 64 KB
        self.logger = logger or logging.getLogger("AppManager.Engine")
        self.rule_engine = RuleEngine(rules_path=rules_path, logger=self.logger)

    def scan_directory(
        self,
        target_dir: Union[str, Path],
        recursive: bool = True,
        show_progress: bool = True,
    ) -> List[Path]:
        """
        Traverse target directory and collect regular file paths safely.
        Resilient against Windows permission errors, system-protected directories,
        and unreadable files.
        """
        root_path = normalize_path(target_dir)
        if not root_path.exists():
            self.logger.error("Target scan directory does not exist: %s", root_path)
            raise FileNotFoundError(f"Target scan directory does not exist: {root_path}")

        if not root_path.is_dir():
            self.logger.error("Target scan path is not a directory: %s", root_path)
            raise NotADirectoryError(f"Target scan path is not a directory: {root_path}")

        self.logger.info("Scanning directory: %s (recursive=%s)", root_path, recursive)
        collected_files: List[Path] = []
        scanned_count = 0
        skipped_count = 0

        # Guarded error handler for os.walk against protected system folders
        def handle_walk_error(err: OSError) -> None:
            nonlocal skipped_count
            skipped_count += 1
            self.logger.warning("Access denied or skipping protected directory '%s': %s", getattr(err, "filename", "unknown"), err)

        if recursive:
            for root, dirs, files in os.walk(str(root_path), topdown=True, onerror=handle_walk_error, followlinks=False):
                current_dir = Path(root)
                for filename in files:
                    file_path = current_dir / filename
                    try:
                        # Guard against broken symlinks and permission-restricted file entries
                        if file_path.is_file() and not file_path.is_symlink():
                            collected_files.append(file_path)
                            scanned_count += 1
                        elif file_path.is_symlink():
                            if file_path.exists() and file_path.is_file():
                                collected_files.append(file_path)
                                scanned_count += 1
                            else:
                                skipped_count += 1
                        else:
                            skipped_count += 1
                    except (PermissionError, FileNotFoundError, OSError) as err:
                        self.logger.warning("Permission denied or inaccessible file '%s': %s", file_path, err)
                        skipped_count += 1

                if show_progress and sys.stdout.isatty() and scanned_count % 100 == 0 and scanned_count > 0:
                    sys.stdout.write(f"\rScanning: Discovered {scanned_count} files across directory tree...")
                    sys.stdout.flush()
        else:
            try:
                for entry in root_path.iterdir():
                    try:
                        if entry.is_file():
                            collected_files.append(entry)
                            scanned_count += 1
                    except (PermissionError, FileNotFoundError, OSError) as err:
                        self.logger.warning("Inaccessible entry '%s': %s", entry, err)
                        skipped_count += 1
            except (PermissionError, OSError) as err:
                self.logger.error("Permission denied reading directory contents of '%s': %s", root_path, err)

        if show_progress and sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 75 + "\r")
            sys.stdout.flush()

        self.logger.info(
            "Scan complete: Found %d candidate files in '%s' (skipped %d inaccessible/protected entries).",
            scanned_count, root_path, skipped_count
        )
        return collected_files

    def compute_sha256(
        self,
        file_path: Union[str, Path],
        chunk_size: Optional[int] = None
    ) -> Optional[str]:
        """
        Compute SHA-256 cryptographic hash of a file using memory-buffered chunked streaming.
        Uses 64 KB buffer (default) to safely process multi-gigabyte files with low RAM usage.
        """
        p = normalize_path(file_path)
        buf_size = chunk_size if chunk_size and chunk_size > 0 else self.chunk_size
        hasher = hashlib.sha256()

        try:
            start_time = time.perf_counter()
            with open(p, "rb") as f:
                while chunk := f.read(buf_size):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.debug(
                "SHA-256 generated for '%s' in %.2f ms [Hash: %s...]",
                p.name, elapsed_ms, digest[:12]
            )
            return digest
        except PermissionError as err:
            self.logger.warning("Permission denied reading '%s' for SHA-256 calculation: %s", p, err)
            return None
        except FileNotFoundError as err:
            self.logger.warning("File not found during SHA-256 calculation '%s': %s", p, err)
            return None
        except OSError as err:
            self.logger.warning("OS error reading '%s' for SHA-256 calculation: %s", p, err)
            return None

    def find_duplicates(
        self,
        target_dir: Union[str, Path],
        recursive: bool = True,
        show_progress: bool = True,
    ) -> Tuple[Dict[str, List[FileRecord]], List[FileRecord]]:
        """
        Identify duplicate files via byte-size pre-filtering and SHA-256 chunked hashing.

        Workflow:
        1. Scan files in target directory.
        2. Group files by byte size.
        3. Filter out unique sizes (0 hashes computed for files with unique size).
        4. For candidate size groups (>1 file), compute SHA-256 hashes with progress bar.
        5. Group candidates by SHA-256 hash.
        6. Filter true duplicates (hash group length > 1) and categorize each instance.

        Returns:
            Tuple of (duplicates_dict, all_scanned_file_records)
        """
        files = self.scan_directory(target_dir, recursive=recursive, show_progress=show_progress)
        if not files:
            self.logger.info("No files found to analyze in '%s'.", target_dir)
            return {}, []

        self.logger.info("Step 1/3: Grouping %d files by byte size...", len(files))
        size_groups: Dict[int, List[Path]] = {}
        file_mtimes: Dict[Path, float] = {}
        all_scanned_records: List[FileRecord] = []

        for file_path in files:
            try:
                stat_result = file_path.stat()
                file_size = stat_result.st_size
                mtime = stat_result.st_mtime
                size_groups.setdefault(file_size, []).append(file_path)
                file_mtimes[file_path] = mtime
                # Categorize all scanned files for comprehensive reporting
                category = self.rule_engine.categorize(file_path)
                all_scanned_records.append(
                    FileRecord(path=file_path, size=file_size, category=category, modified_time=mtime)
                )
            except (PermissionError, FileNotFoundError, OSError) as err:
                self.logger.warning("Failed to stat file '%s': %s. Skipping from duplicate check.", file_path, err)

        # Performance optimization: pre-filter unique sizes
        candidate_groups = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
        unique_file_count = sum(len(paths) for size, paths in size_groups.items() if len(paths) == 1)
        candidate_file_count = sum(len(paths) for paths in candidate_groups.values())

        self.logger.info(
            "Step 2/3: Size pre-filter complete. Skipped hashing %d unique-sized files. "
            "Proceeding to hash %d candidate files across %d matching size groups.",
            unique_file_count, candidate_file_count, len(candidate_groups)
        )

        if not candidate_groups:
            self.logger.info("No size collisions detected. Zero duplicate files exist.")
            return {}, all_scanned_records

        self.logger.info("Step 3/3: Computing SHA-256 hashes on candidate size collision groups...")
        hash_groups: Dict[str, List[FileRecord]] = {}
        hashes_calculated = 0

        # Visual progress bar for candidate SHA-256 hashing
        progress_bar = ProgressBar(
            total=candidate_file_count,
            prefix="Hashing Candidates",
            logger=self.logger
        ) if show_progress else None

        for file_size, paths in candidate_groups.items():
            for path in paths:
                if progress_bar:
                    progress_bar.update(hashes_calculated, item_name=path.name)

                sha256 = self.compute_sha256(path)
                hashes_calculated += 1

                if progress_bar:
                    progress_bar.update(hashes_calculated, item_name=path.name)

                if sha256 is None:
                    continue  # Unreadable file

                category = self.rule_engine.categorize(path)
                mtime = file_mtimes.get(path, 0.0)

                record = FileRecord(
                    path=path,
                    size=file_size,
                    category=category,
                    sha256_hash=sha256,
                    modified_time=mtime,
                )
                hash_groups.setdefault(sha256, []).append(record)

        if progress_bar:
            progress_bar.finish("SHA-256 candidate hashing completed.")

        # Retain only actual duplicate groups (groups with >1 file with identical SHA-256)
        true_duplicates: Dict[str, List[FileRecord]] = {
            h: records for h, records in hash_groups.items() if len(records) > 1
        }

        total_duplicate_files = sum(len(records) for records in true_duplicates.values())
        wasted_bytes = sum(
            (len(records) - 1) * records[0].size for records in true_duplicates.values()
        )

        self.logger.info(
            "Duplicate analysis finished: Calculated %d SHA-256 hashes. "
            "Identified %d duplicate sets containing %d total files (Redundant space: %s).",
            hashes_calculated, len(true_duplicates), total_duplicate_files, format_bytes(wasted_bytes)
        )

        return true_duplicates, all_scanned_records

    def delete_file(
        self,
        file_path: Union[str, Path],
        dry_run: bool = False
    ) -> bool:
        """
        Safely delete an individual file with logging and error handling.
        """
        p = normalize_path(file_path)
        if dry_run:
            self.logger.info("[DRY-RUN] Simulated deletion of file: %s", p)
            return True

        if not p.exists():
            self.logger.warning("Attempted to delete non-existent file: %s", p)
            return False

        try:
            p.unlink()
            self.logger.info("Successfully deleted duplicate file: %s", p)
            return True
        except PermissionError as err:
            self.logger.error("Permission denied attempting to delete '%s': %s", p, err)
            return False
        except OSError as err:
            self.logger.error("OS error deleting file '%s': %s", p, err)
            return False

    def batch_delete_files(
        self,
        file_paths: Sequence[Union[str, Path]],
        dry_run: bool = False
    ) -> Dict[Path, bool]:
        """
        Safely delete a sequence of files, returning status mapping for each.
        """
        results: Dict[Path, bool] = {}
        for fp in file_paths:
            path_obj = normalize_path(fp)
            success = self.delete_file(path_obj, dry_run=dry_run)
            results[path_obj] = success
        return results


# ============================================================================
# CLI & Terminal Presentation Layer
# ============================================================================

def print_banner() -> None:
    """Print ASCII header for CLI interface."""
    banner = r"""
================================================================================
          Intelligent Application Manager & Duplicate Resolver
             Byte-Level Content Detection & Rule Categorization
================================================================================
"""
    print(banner)


def display_duplicate_summary(duplicates: Dict[str, List[FileRecord]]) -> None:
    """Display tabular / formatted summary of identified duplicates."""
    if not duplicates:
        print("\n[+] No duplicate files found. Workspace is clean!")
        return

    total_groups = len(duplicates)
    total_files = sum(len(records) for records in duplicates.values())
    wasted_bytes = sum((len(records) - 1) * records[0].size for records in duplicates.values())

    print("\n" + "=" * 80)
    print(f" IDENTIFIED DUPLICATE SETS ({total_groups} Groups | {total_files} Files | Reclaimable: {format_bytes(wasted_bytes)})")
    print("=" * 80)

    for idx, (sha256, records) in enumerate(duplicates.items(), start=1):
        file_size = records[0].size
        group_wasted = (len(records) - 1) * file_size
        print(f"\nGroup #{idx} [SHA-256: {sha256}]")
        print(f"  Size per file: {format_bytes(file_size)} | Redundant Waste: {format_bytes(group_wasted)}")
        print("  Files:")
        for file_idx, record in enumerate(records, start=1):
            mtime_str = time.strftime(DATE_FORMAT, time.localtime(record.modified_time))
            print(f"    [{file_idx}] {record.path}")
            print(f"        Category: {record.category:<24} | Modified: {mtime_str}")

    print("\n" + "-" * 80)


def display_category_breakdown_table(
    scanned_records: List[FileRecord],
    duplicates: Dict[str, List[FileRecord]],
    reclaimed_bytes: int = 0
) -> None:
    """
    Render a clean summary table displaying total applications scanned,
    duplicate space reclaimed, and breakdown across all configured categories.
    """
    # Aggregate statistics per category
    category_scanned_count: Dict[str, int] = {}
    category_scanned_bytes: Dict[str, int] = {}
    category_dup_count: Dict[str, int] = {}
    category_dup_groups: Dict[str, int] = {}
    category_waste_bytes: Dict[str, int] = {}

    for rec in scanned_records:
        cat = rec.category
        category_scanned_count[cat] = category_scanned_count.get(cat, 0) + 1
        category_scanned_bytes[cat] = category_scanned_bytes.get(cat, 0) + rec.size

    for sha256, records in duplicates.items():
        if not records:
            continue
        primary_cat = records[0].category
        file_size = records[0].size
        group_waste = (len(records) - 1) * file_size

        category_dup_groups[primary_cat] = category_dup_groups.get(primary_cat, 0) + 1
        category_dup_count[primary_cat] = category_dup_count.get(primary_cat, 0) + len(records)
        category_waste_bytes[primary_cat] = category_waste_bytes.get(primary_cat, 0) + group_waste

    # Collect all unique categories
    all_categories = sorted(
        set(category_scanned_count.keys()) | set(category_dup_count.keys())
    )

    total_scanned_files = len(scanned_records)
    total_scanned_bytes = sum(r.size for r in scanned_records)
    total_dup_files = sum(len(r) for r in duplicates.values())
    total_dup_groups = len(duplicates)
    total_redundant_bytes = sum((len(r) - 1) * r[0].size for r in duplicates.values())

    table_width = 88
    print("\n" + "=" * table_width)
    print("                     APPLICATION SCAN & CATEGORY BREAKDOWN")
    print("=" * table_width)
    header = f"{'Category':<26} {'Scanned':>9} {'Total Size':>12} {'Dup Files':>11} {'Dup Groups':>12} {'Redundant Space':>15}"
    print(header)
    print("-" * table_width)

    for cat in all_categories:
        scanned_cnt = category_scanned_count.get(cat, 0)
        scanned_sz = format_bytes(category_scanned_bytes.get(cat, 0))
        dup_cnt = category_dup_count.get(cat, 0)
        dup_grp = category_dup_groups.get(cat, 0)
        waste_sz = format_bytes(category_waste_bytes.get(cat, 0))
        print(f"{cat:<26} {scanned_cnt:>9} {scanned_sz:>12} {dup_cnt:>11} {dup_grp:>12} {waste_sz:>15}")

    print("-" * table_width)
    totals_row = (
        f"{'TOTALS':<26} {total_scanned_files:>9} {format_bytes(total_scanned_bytes):>12} "
        f"{total_dup_files:>11} {total_dup_groups:>12} {format_bytes(total_redundant_bytes):>15}"
    )
    print(totals_row)
    print("=" * table_width)

    if reclaimed_bytes > 0:
        print(f"[+] Reclaimed Disk Space: {format_bytes(reclaimed_bytes)}")
    print()


def interactive_duplicate_resolution(
    duplicates: Dict[str, List[FileRecord]],
    manager: ApplicationManager,
    all_scanned_records: List[FileRecord],
    dry_run: bool = False
) -> int:
    """
    Interactive prompt loop allowing the user to inspect each duplicate group
    and explicitly select which instances to delete or keep.
    Returns total bytes reclaimed.
    """
    if not duplicates:
        display_category_breakdown_table(all_scanned_records, duplicates)
        return 0

    print_banner()
    display_duplicate_summary(duplicates)

    if dry_run:
        print("\n[!] RUNNING IN DRY-RUN MODE: No files will actually be deleted from disk.\n")

    print("\nResolution Commands for each duplicate group:")
    print("  keep <N>         : Keep file index <N> and delete all other copies in group")
    print("  delete <N1,N2...>: Delete specific file indices (comma separated, e.g. '2, 3')")
    print("  keep-newest      : Automatically keep the newest modified file and delete others")
    print("  keep-oldest      : Automatically keep the oldest modified file and delete others")
    print("  skip / s         : Skip this duplicate group (keep all files)")
    print("  quit / q         : Abort and exit resolution tool\n")

    files_staged_for_deletion: List[FileRecord] = []

    group_list = list(duplicates.items())
    for group_num, (sha256, records) in enumerate(group_list, start=1):
        print("=" * 80)
        print(f" Resolving Duplicate Group {group_num}/{len(group_list)} [SHA-256: {sha256[:16]}...]")
        print(f" File Size: {records[0].formatted_size} | Total Instances: {len(records)}")
        print("=" * 80)

        for file_idx, record in enumerate(records, start=1):
            mtime_str = time.strftime(DATE_FORMAT, time.localtime(record.modified_time))
            print(f"  [{file_idx}] {record.path}")
            print(f"      Category: {record.category} | Modified: {mtime_str}")

        while True:
            try:
                prompt_input = input(f"\nSelect action for Group #{group_num} [keep <N> / delete <N...> / keep-newest / keep-oldest / skip / quit]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[!] Resolution aborted by user.")
                display_category_breakdown_table(all_scanned_records, duplicates)
                return 0

            if not prompt_input:
                continue

            cmd_parts = prompt_input.split(maxsplit=1)
            action = cmd_parts[0].lower()
            arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

            if action in ("quit", "q", "exit"):
                print("\n[!] Exiting resolution. No pending deletions from this group onward.")
                break

            if action in ("skip", "s"):
                print(f"[+] Skipped Group #{group_num}. All {len(records)} files preserved.")
                break

            if action == "keep":
                if not arg.isdigit():
                    print("[X] Invalid file number. Example: 'keep 1'")
                    continue
                keep_idx = int(arg)
                if keep_idx < 1 or keep_idx > len(records):
                    print(f"[X] Index out of range. Must be between 1 and {len(records)}.")
                    continue

                for i, rec in enumerate(records, start=1):
                    if i != keep_idx:
                        files_staged_for_deletion.append(rec)
                print(f"[+] Staged {len(records) - 1} duplicate(s) for deletion (Keeping instance [{keep_idx}]).")
                break

            elif action == "delete":
                if not arg:
                    print("[X] Please provide comma-separated file indices to delete. Example: 'delete 2, 3'")
                    continue
                raw_indices = [x.strip() for x in arg.replace(" ", ",").split(",") if x.strip()]
                valid = True
                selected_indices: Set[int] = set()
                for token in raw_indices:
                    if not token.isdigit():
                        print(f"[X] Invalid index '{token}'. Must be numeric.")
                        valid = False
                        break
                    idx = int(token)
                    if idx < 1 or idx > len(records):
                        print(f"[X] Index {idx} out of range (1 - {len(records)}).")
                        valid = False
                        break
                    selected_indices.add(idx)

                if not valid:
                    continue

                if len(selected_indices) == len(records):
                    print("[!] WARNING: You selected ALL instances for deletion. You must keep at least one copy!")
                    continue

                for i, rec in enumerate(records, start=1):
                    if i in selected_indices:
                        files_staged_for_deletion.append(rec)
                print(f"[+] Staged {len(selected_indices)} duplicate(s) for deletion.")
                break

            elif action == "keep-newest":
                sorted_records = sorted(records, key=lambda r: r.modified_time, reverse=True)
                newest_record = sorted_records[0]
                for rec in records:
                    if rec != newest_record:
                        files_staged_for_deletion.append(rec)
                print(f"[+] Staged {len(records) - 1} older duplicate(s) for deletion (Keeping newest: {newest_record.path.name}).")
                break

            elif action == "keep-oldest":
                sorted_records = sorted(records, key=lambda r: r.modified_time)
                oldest_record = sorted_records[0]
                for rec in records:
                    if rec != oldest_record:
                        files_staged_for_deletion.append(rec)
                print(f"[+] Staged {len(records) - 1} newer duplicate(s) for deletion (Keeping oldest: {oldest_record.path.name}).")
                break

            else:
                print(f"[X] Unrecognized command '{prompt_input}'. Type 'keep 1', 'delete 2', 'keep-newest', 'skip', or 'quit'.")

        if action in ("quit", "q", "exit"):
            break

    # =========================================================================
    # Final Confirmation & Deletion Execution
    # =========================================================================
    if not files_staged_for_deletion:
        print("\n[+] No files were marked for deletion. Existing files remain untouched.")
        display_category_breakdown_table(all_scanned_records, duplicates)
        return 0

    staged_bytes = sum(f.size for f in files_staged_for_deletion)
    print("\n" + "=" * 80)
    print(f" DELETION CONFIRMATION ({len(files_staged_for_deletion)} Files | Reclaimable Space: {format_bytes(staged_bytes)})")
    print("=" * 80)
    for idx, rec in enumerate(files_staged_for_deletion, start=1):
        print(f"  [{idx}] {rec.path} ({rec.formatted_size}) [{rec.category}]")

    print("=" * 80)
    if dry_run:
        print("[!] DRY-RUN MODE ENABLED: Files will NOT be deleted.")

    try:
        confirm = input("\nAre you sure you want to permanently delete these files? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[!] Deletion cancelled. No files were removed.")
        display_category_breakdown_table(all_scanned_records, duplicates)
        return 0

    reclaimed_bytes = 0
    if confirm in ("y", "yes"):
        print("\nExecuting deletions...")
        deleted_count = 0
        failed_count = 0

        for rec in files_staged_for_deletion:
            success = manager.delete_file(rec.path, dry_run=dry_run)
            if success:
                deleted_count += 1
                reclaimed_bytes += rec.size
                status = "[SIMULATED]" if dry_run else "[DELETED]"
                print(f"  {status} {rec.path}")
            else:
                failed_count += 1
                print(f"  [FAILED]  {rec.path}")

        print("\n" + "=" * 80)
        action_verb = "Simulated deletion of" if dry_run else "Successfully deleted"
        print(f"[+] {action_verb} {deleted_count} files (Freed: {format_bytes(reclaimed_bytes)}). Failed: {failed_count}.")
        print("=" * 80)
    else:
        print("\n[!] Deletion aborted by user. No files were removed.")

    display_category_breakdown_table(all_scanned_records, duplicates, reclaimed_bytes=reclaimed_bytes)
    return reclaimed_bytes


# ============================================================================
# CLI Argument Parser & Entry Point
# ============================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Intelligent Application Management & Content-Based Duplicate Resolver.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py --dir ./my_applications
  python app.py --dir C:/Projects --rules ./rules.json --dry-run
  python app.py --dir ./downloads --log-file scan.log --log-level DEBUG
        """
    )
    parser.add_argument(
        "-d", "--dir",
        dest="directory",
        type=str,
        default=".",
        help="Target directory to scan for duplicate applications (default: current directory)."
    )
    parser.add_argument(
        "-r", "--rules",
        dest="rules_file",
        type=str,
        default=DEFAULT_RULES_FILE,
        help=f"Path to JSON categorization rules file (default: {DEFAULT_RULES_FILE})."
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        default=True,
        help="Disable recursive sub-directory scanning (default: recursive is enabled)."
    )
    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Byte buffer size for SHA-256 chunked streaming (default: {DEFAULT_CHUNK_SIZE} bytes / 64 KB)."
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Simulate duplicate resolution without deleting any files on disk."
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)."
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=str,
        default=None,
        help="Optional file path to persist structured operational logs."
    )
    parser.add_argument(
        "--scan-only",
        dest="scan_only",
        action="store_true",
        default=False,
        help="Only scan and report duplicates without launching interactive resolution prompt."
    )
    parser.add_argument(
        "--no-progress",
        dest="show_progress",
        action="store_false",
        default=True,
        help="Disable visual console progress bar."
    )
    return parser


def main() -> int:
    """CLI application entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    logger = setup_logging(log_level=args.log_level, log_file=args.log_file)
    logger.info("Initializing Application Manager...")

    try:
        manager = ApplicationManager(
            rules_path=args.rules_file,
            chunk_size=args.chunk_size,
            logger=logger,
        )
    except Exception as err:
        logger.critical("Initialization error: %s", err, exc_info=True)
        return 1

    try:
        duplicates, scanned_records = manager.find_duplicates(
            target_dir=args.directory,
            recursive=args.recursive,
            show_progress=args.show_progress,
        )
    except (FileNotFoundError, NotADirectoryError) as err:
        logger.error("Scan aborted: %s", err)
        return 1
    except Exception as err:
        logger.error("Unexpected error during duplicate scanning: %s", err, exc_info=True)
        return 1

    if args.scan_only:
        print_banner()
        display_duplicate_summary(duplicates)
        display_category_breakdown_table(scanned_records, duplicates)
        return 0

    interactive_duplicate_resolution(
        duplicates=duplicates,
        manager=manager,
        all_scanned_records=scanned_records,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
