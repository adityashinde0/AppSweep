# JP-001 Duplicate Application Manager — Project Progress & Context

This document tracks the project state, completed architecture, codebase directory structure, verification records, and run instructions so any developer or AI model can seamlessly resume work without context loss.

---

## 📌 Project Overview
**JP-001 Duplicate Application Manager** is a production-grade application management and duplicate detection system. It identifies duplicate standalone applications and multi-file application bundles based on **byte-level cryptographic content fingerprints** (not filenames, extensions, or timestamps), categorizes applications using dynamic rule configurations, and provides safe quarantine/1-click restoration capabilities.

---

## 🚦 Current Status: `COMPLETE & VERIFIED` (MVP / Production-Ready)

| Module / Layer | Status | Tests Passed | Key Deliverables |
|---|---|---|---|
| **1. Standalone CLI Tool** | ✅ Complete | 30 / 30 | `app.py`, `rules.json`, `test_app.py` |
| **2. Database & Schema** | ✅ Complete | Verified | 8 SQLAlchemy tables (`core/models.py`, `core/database.py`) |
| **3. Content Fingerprinting & Scan Engine** | ✅ Complete | Verified | 64 KB memory-buffered SHA-256 streaming, candidate size filter (`services/scan_service.py`) |
| **4. Quarantine & Restoration Manager** | ✅ Complete | Verified | Preview, atomic move to `.quarantine/<id>/`, 1-click restore (`services/quarantine_manager.py`) |
| **5. Categorization Rule Engine** | ✅ Complete | Verified | Extension, word-boundary keyword, and glob path pattern matching (`services/rule_engine.py`) |
| **6. FastAPI REST Backend** | ✅ Complete | 7 / 7 | Routers for scans, apps, duplicates, removals, rules, audit logs (`api/`) |
| **7. Stitch Web UI Frontend** | ✅ Complete | Verified | Single-page dashboard, side-by-side duplicate review cards, quarantine manager (`static/`) |
| **8. Demo Sandbox & Seed Harness** | ✅ Complete | Verified | `seed_demo.py`, `run_server.py` |

---

## 📁 Codebase Directory Structure & Map

```
c:\Users\Tulsi.Y.Kumbhar\MyProj\
├── api/
│   ├── routers/
│   │   ├── apps.py            # GET /api/apps, GET /api/apps/{id}
│   │   ├── audit.py           # GET /api/audit (event ledger)
│   │   ├── duplicates.py      # GET /api/duplicates, GET /api/duplicates/{id}
│   │   ├── removals.py        # POST /api/removals/preview, POST /api/removals, POST /api/removals/{id}/restore
│   │   ├── rules.py           # Full CRUD for categorization rules (/api/rules)
│   │   └── scans.py           # POST /api/scans, GET /api/scans/{id}, POST /api/scans/{id}/cancel
│   └── main.py                # FastAPI app initialization, CORS, static UI mounts, health & stats endpoints
│
├── core/
│   ├── config.py              # Pydantic Settings, environment variables, quarantine dir, path security validator
│   ├── database.py            # SQLAlchemy engine, SessionLocal, init_db(), automatic rule seeding
│   ├── models.py              # 8 SQLAlchemy models (ScanJob, Application, AppFile, DuplicateGroup, DuplicateGroupMember, CategorizationRule, RemovalAction, AuditLog)
│   └── schemas.py             # Pydantic v2 validation models for all API requests and responses
│
├── services/
│   ├── audit_service.py       # Append-only structured audit logging helper
│   ├── quarantine_manager.py  # Safety preview, atomic quarantine move, reverse restoration
│   ├── rule_engine.py         # Dynamic rule evaluation with word-boundary keyword matching
│   └── scan_service.py        # Background scan worker, 64 KB chunked hashing, deterministic fingerprint formula
│
├── static/                    # Stitch Web UI (Vanilla HTML/CSS/JS)
│   ├── css/
│   │   └── styles.css         # Dark glassmorphism design system & responsive UI layout
│   ├── js/
│   │   └── app.js             # Client-side reactive SPA controller, API integrations, live scan polling
│   └── index.html             # Single-page dashboard (Dashboard, Duplicate Review, Catalog, Quarantine, Rules, Audit)
│
├── .antigravity               # Assistant workflow and communication efficiency rules
├── app.py                     # Standalone terminal CLI scanner and duplicate resolver
├── rules.json                 # Default categorization rules for CLI tool
├── run_server.py              # Development server launcher (FastAPI + Uvicorn)
├── seed_demo.py               # Demo sandbox generator (simulates duplicates for judges)
├── test_api.py                # Integration test suite for REST API & Services (7 tests)
├── test_app.py                # Unit test suite for CLI Engine (30 tests)
├── ARCHITECTURE.md            # System architecture and schema design document
├── PRD.md                     # Product requirements document
└── progress.md                # (This file) Project status and context handover document
```

---

## 🔑 Core Technical Decisions & Formulas

1. **Content Fingerprint Calculation**:
   - Single-file applications: $\text{SHA-256}(\text{"app"} : \text{size} : \text{file\_sha256})$ (matches identical files regardless of renaming).
   - Multi-file bundles: Deterministic SHA-256 calculated over sorted list of $\text{rel\_path} : \text{size} : \text{sha256}$.
2. **Chunked Memory-Buffered Hashing**:
   - Standard 64 KB (`65,536` bytes) chunks to safely hash large application installers without RAM spikes.
3. **Database Dialect Strategy**:
   - Dual-dialect compatibility: Connects to Supabase PostgreSQL when `DATABASE_URL` is set; automatically falls back to local SQLite (`sqlite:///./jp001_local.db`) for zero-config local development.
4. **Safety & Guardrails**:
   - Reversible quarantine (`.quarantine/<action_id>/`) with full 1-click restore.
   - Symlink protection and path traversal checks against configured allowed roots.
   - Non-destructive default: Deletion/quarantine always requires explicit confirmation.

---

## 🏃 Commands Quick Reference

### Launch Web Server & Dashboard
```powershell
python run_server.py
# Open Dashboard: http://127.0.0.1:8000
# Open Swagger Docs: http://127.0.0.1:8000/docs
```

### Run Interactive CLI Tool
```powershell
python app.py ./demo_sandbox
```

### Seed Demo Sandbox (Sample duplicate applications)
```powershell
python seed_demo.py
```

### Run Test Suites
```powershell
# 1. Full-Stack API & Services Suite
python -m unittest test_api.py -v

# 2. Standalone CLI Engine Suite
python -m unittest test_app.py -v
```

---

## 📝 Recent Activity Log
- **2026-08-29**:
  - Implemented standalone CLI prototype (`app.py`, `rules.json`, `test_app.py` - 30/30 passed).
  - Architected and built complete FastAPI full-stack backend with 8 SQL tables (`core/models.py`, `core/schemas.py`).
  - Built `services/scan_service.py`, `services/quarantine_manager.py`, `services/rule_engine.py`, `services/audit_service.py`.
  - Built 6 REST API routers (`api/routers/`) and mounted Stitch Web UI (`static/`).
  - Added integration test suite (`test_api.py` - 7/7 passed).
  - Seeded `./demo_sandbox` and verified end-to-end functionality on local server (`http://127.0.0.1:8000`).
