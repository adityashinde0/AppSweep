"""
Demo data seeder for JP-001 Duplicate Application Manager.
Creates realistic duplicate applications, bundles, and binaries in ./demo_sandbox for demo judges.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from core.database import init_db


def seed_demo_environment() -> Path:
    """Generate sample application directories and files for live demo evaluation."""
    sandbox_dir = Path("./demo_sandbox").resolve()
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)

    print("Generating demo sandbox directory structure at:", sandbox_dir)

    # 1. Multi-file Developer Tool Bundle (Duplicate 1)
    dev_app1 = sandbox_dir / "Applications" / "CodeEditor_v1.2"
    dev_app2 = sandbox_dir / "Backup" / "CodeEditor_v1.2_Copy"
    dev_app1.mkdir(parents=True, exist_ok=True)
    dev_app2.mkdir(parents=True, exist_ok=True)

    code_binary = b"\x7fELF\x02\x01\x01\x00" + (b"CodeEditorCoreBinaryPayload" * 150)
    code_config = b'{"theme": "dark", "version": "1.2.0", "plugins": ["python", "git"]}'

    (dev_app1 / "code_editor.exe").write_bytes(code_binary)
    (dev_app1 / "settings.json").write_bytes(code_config)

    (dev_app2 / "code_editor.exe").write_bytes(code_binary)
    (dev_app2 / "settings.json").write_bytes(code_config)

    # 2. Media Player Application (Duplicate 2)
    media_app1 = sandbox_dir / "MediaTools" / "vlc_player.exe"
    media_app2 = sandbox_dir / "Downloads" / "vlc_player_installer.exe"
    media_app1.parent.mkdir(parents=True, exist_ok=True)
    media_app2.parent.mkdir(parents=True, exist_ok=True)

    media_binary = b"\x4d\x5a\x90\x00" + (b"VLCVideoDecoderAudioStreamData" * 300)
    media_app1.write_bytes(media_binary)
    media_app2.write_bytes(media_binary)

    # 3. Game Package (Duplicate 3)
    game_app1 = sandbox_dir / "Games" / "RetroArcade" / "game.rom"
    game_app2 = sandbox_dir / "Emulators" / "RetroArcade_Backup" / "game.rom"
    game_app1.parent.mkdir(parents=True, exist_ok=True)
    game_app2.parent.mkdir(parents=True, exist_ok=True)

    game_payload = b"RETRO_ARCADE_ROM_HEADER" + (b"LevelData_Tilemap_SoundTrack" * 100)
    game_app1.write_bytes(game_payload)
    game_app2.write_bytes(game_payload)

    # 4. Same Size Different Content Collision (Non-Duplicates)
    tools_dir = sandbox_dir / "SystemTools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "driver_alpha.sys").write_bytes(b"A" * 128)
    (tools_dir / "driver_beta.sys").write_bytes(b"B" * 128)

    # 5. Unique Applications
    (sandbox_dir / "Documents" / "annual_financial_report.pdf").parent.mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "Documents" / "annual_financial_report.pdf").write_bytes(b"%PDF-1.4 ReportContentUnique" * 50)

    (tools_dir / "cleaner_utility.exe").write_bytes(b"SystemCleanerUtilityBinaryPayload" * 80)

    print("Demo sandbox successfully created with 3 duplicate sets and 3 unique items.")
    return sandbox_dir


if __name__ == "__main__":
    init_db()
    seed_demo_environment()
