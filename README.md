# AppSweep (JP-001 Duplicate Application Manager)

> **Intelligent, byte-level cryptographic content detection, categorization, and safe quarantine management for duplicate applications and bundles.**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-42%2F42%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## 📌 Overview

**AppSweep** is an application management and duplicate detection engine. Unlike traditional cleaners that rely on unreliable heuristics such as filenames, file extensions, or modified timestamps, AppSweep identifies duplicates using **byte-level cryptographic content fingerprints** (SHA-256).

Whether duplicate executables have been renamed, moved to nested directories, or bundled across multi-file structures, AppSweep detects identical builds, categorizes them according to dynamic rules, and provides a safe, reversible quarantine and restoration workflow.

---

## ✨ Key Features

- **Byte-Level Cryptographic Fingerprints**:
  - Standalone binaries: Content SHA-256 with candidate size pre-filtering.
  - Multi-file bundles: Deterministic compound hash derived from sorted relative paths, sizes, and file SHA-256 checksums.
- **Size Pre-Filtering & Chunked Hashing**:
  - Groups candidates by exact byte size before hashing to eliminate unnecessary disk I/O.
  - Streams data in 64 KB memory buffers to ensure minimal RAM usage even on large executables.
- **Dynamic Categorization Rule Engine**:
  - Automatically classifies applications (e.g., Development, Media, Games, Utilities) using word-boundary keyword matching, extensions, and glob patterns.
- **Safe Reversible Quarantine & Restoration**:
  - Zero irreversible deletions by default.
  - Redundant items are staged and moved atomically to `.quarantine/<action_id>/` with 1-click full restoration.
- **Append-Only Audit Ledger**:
  - Full traceability for all scan, quarantine, and restoration actions.
- **Dual Interfaces**:
  - **Modern Web Dashboard**: Responsive dark glassmorphism UI with live scan progress polling, duplicate side-by-side inspection, and quarantine manager.
  - **Standalone Interactive CLI**: Zero-dependency terminal interface with batch commands (`keep <N>`, `keep-newest`, `keep-oldest`, `delete <N>`).
- **Zero-Config Database**:
  - Seamlessly runs out-of-the-box on local SQLite (`sqlite:///./jp001_local.db`), or connects to Supabase / PostgreSQL via environment variables.

---

## 📁 Repository Structure

```text
AppSweep/
├── api/
│   ├── routers/
│   │   ├── apps.py            # Endpoints: GET /api/apps, GET /api/apps/{id}
│   │   ├── audit.py           # Endpoints: GET /api/audit (event ledger)
│   │   ├── duplicates.py      # Endpoints: GET /api/duplicates, GET /api/duplicates/{id}
│   │   ├── removals.py        # Endpoints: POST /api/removals, POST /api/removals/{id}/restore
│   │   ├── rules.py           # Endpoints: CRUD /api/rules (dynamic categorization)
│   │   └── scans.py           # Endpoints: POST /api/scans, GET /api/scans/{id}, cancel
│   └── main.py                # FastAPI initialization, CORS, static file mounts, health stats
│
├── core/
│   ├── config.py              # Application settings, path traversal & safety guards
│   ├── database.py            # SQLAlchemy engine, SessionLocal, auto table initialization
│   ├── models.py              # 8 SQLAlchemy models (ScanJob, Application, DuplicateGroup, etc.)
│   └── schemas.py             # Pydantic v2 schemas for request/response validation
│
├── services/
│   ├── audit_service.py       # Append-only structured audit logging helper
│   ├── quarantine_manager.py  # Safety preview, atomic quarantine move, reverse restoration
│   ├── rule_engine.py         # Dynamic rule evaluation with word-boundary keyword matching
│   └── scan_service.py        # Multi-stage file discovery and chunked SHA-256 fingerprinting
│
├── static/                    # Web UI Frontend (Vanilla HTML5 / CSS3 / ES6 JavaScript)
│   ├── css/
│   │   └── styles.css         # Dark glassmorphism design system & responsive layout
│   ├── js/
│   │   └── app.js             # Reactive SPA controller, API integrations, polling
│   └── index.html             # Single-page application dashboard
│
├── app.py                     # Standalone terminal CLI scanner and duplicate resolver
├── rules.json                 # Default categorization rules for CLI tool
├── run_server.py              # Development server launcher (FastAPI + Uvicorn)
├── seed_demo.py               # Demo sandbox generator (simulates sample duplicate files)
├── test_api.py                # Integration test suite for REST API & Services
├── test_app.py                # Unit test suite for CLI Engine
├── requirements.txt           # Project Python dependencies
├── ARCHITECTURE.md            # Deep-dive architecture and database schema design
├── PRD.md                     # Product requirements document
└── progress.md                # Project status, milestones, and development log
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/adityashinde0/AppSweep.git
cd AppSweep
```

### 3. Set Up Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Generate Demo Data (Optional)
To test duplicate detection with pre-populated dummy applications:
```bash
python seed_demo.py
```
*(Creates a sample `./demo_sandbox` directory populated with duplicate binaries and bundles)*

---

## 💻 Running the Application

### Option A: Web Dashboard & REST API
Start the FastAPI server:
```bash
python run_server.py
```
- **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Option B: Standalone Terminal CLI
Run the CLI tool directly on any directory:
```bash
python app.py ./demo_sandbox
```

#### CLI Resolution Commands:
- `keep <N>`: Keep candidate `#N` and delete/quarantine all other copies in the group.
- `keep-newest`: Automatically keep the file with the most recent modification time.
- `keep-oldest`: Automatically keep the oldest file and mark duplicates.
- `delete <N1,N2...>`: Delete specific indices (e.g. `2, 3`).
- `skip`: Skip current group without modifications.
- `quit`: Abort resolution process safely.

---

## 🧪 Running Tests

AppSweep includes a comprehensive test suite (42 unit and integration tests) covering hashing, rule matching, quarantine/restoration, safety traversal checks, and REST endpoints.

Run all tests:
```bash
python -m unittest discover -v
```

Or run individual suites:
```bash
# REST API & Services Test Suite (7 tests)
python -m unittest test_api.py -v

# Standalone CLI Engine Suite (30 tests)
python -m unittest test_app.py -v
```

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root directory (optional, defaults provided):

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./jp001_local.db` | SQLAlchemy connection URL (SQLite or PostgreSQL / Supabase) |
| `HOST` | `127.0.0.1` | Host address for web server |
| `PORT` | `8000` | Port for web server |
| `DEBUG` | `false` | Enable verbose debug logging & SQL query echoes |
| `QUARANTINE_DIR` | `./.quarantine` | Directory where quarantined files are staged |
| `CHUNK_SIZE` | `65536` (64 KB) | Streaming buffer size for SHA-256 hashing |
| `ALLOWED_ROOTS` | `""` (all local paths) | Semicolon-delimited list of permitted base paths |

---

## 🛡️ Security & Safety Guardrails

- **No Destructive Deletion**: Files moved during resolution are stored in `.quarantine/<action_id>/` and can be restored at any time via the UI or API.
- **Path Traversal Prevention**: All target paths are strictly sanitized and checked against path traversal (`../`) and forbidden characters.
- **Symlink Protection**: Symlinks that escape scanned boundaries are ignored.
- **Read Error Handling**: Unreadable or permission-locked files are recorded as errors in the audit log rather than falsely flagged as duplicate evidence.

---

## 📄 License
This project is licensed under the MIT License.
