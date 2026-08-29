# PRD.md — JP-001 Duplicate Application Manager

## 1. Problem Summary & Core Value Proposition

Applications can be installed multiple times with different names, file types, or timestamps, making filename/metadata-based cleanup unreliable. JP-001 scans application contents, generates cryptographic hashes, and groups installations with matching content fingerprints. It then applies simple, configurable rules to categorize applications and lets users safely review duplicate groups before removal. The 12-hour demo focuses on a trustworthy scan → review → categorize → quarantine flow with clear auditability.

## 2. Target Users & Key Journeys

- **Developer / IT Admin**
  - Configure scan directories → start scan → monitor progress → inspect duplicate groups → select redundant installation → quarantine → review audit log.
- **Power User**
  - Scan common application directories → browse categories → open a duplicate group → compare size/path/hash evidence → remove selected copy.
- **Demo Judge**
  - Launch dashboard → run seeded/real scan → see content-based duplicate evidence → change/apply a categorization rule → safely remove one duplicate → verify audit record.

## 3. MVP Scope — Tier 1 (12-hour demo)

### Must Have
- Python FastAPI backend + Supabase PostgreSQL.
- Configurable local scan directories.
- Recursive file discovery with streaming SHA-256 hashing; avoid loading whole files into memory.
- Application-level content fingerprint derived from normalized relative file paths + file SHA-256 + sizes.
- Duplicate grouping by identical application fingerprint; show supporting file/hash evidence.
- Predefined rule-based categorization (path/name/manifest-derived metadata); CRUD for rules.
- Dashboard: scan status, application count, duplicate count, reclaimable size.
- Duplicate review: compare paths, sizes, file counts, fingerprints.
- **Safe removal:** move selected application to a quarantine directory, not irreversible delete; record action/audit log.
- Scan progress, errors, and resumable/failed status.
- Basic structured logging and validation.

### Explicit Demo Guardrails
- Never auto-delete.
- Require user confirmation for quarantine.
- Restrict scans/removals to configured allowed roots.
- Reject path traversal and symlink escapes.
- Treat unreadable files as scan errors, not duplicate evidence.

## 4. Post-Hackathon Wishlist

- Windows/macOS/Linux application parsers and package-manager integration.
- Incremental hashing/cache and background worker queue.
- Near-duplicate detection (similar contents, not only identical fingerprints).
- Advanced rule engine / visual rule builder.
- Restore-from-quarantine UI and retention policy.
- Authentication/RBAC, multi-device management, signed audit exports.
- Native desktop UI, scheduled scans, notifications, analytics.
- AI-assisted categorization/explanations (optional; never required for core detection).
