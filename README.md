# Stafflyx HR AI Assistant

**Intelligent HR Self-Service Platform — RAG-Powered, Locally Hosted**

Stafflyx HR AI Assistant gives employees instant, personalized answers to HR questions by combining a FAISS vector search index of company documents with live employee data from MySQL, all processed through a local Ollama language model. The system runs entirely on-premises with no external API calls, keeping sensitive HR data within your infrastructure.

---

## Overview

The platform runs two separate interfaces:

- **Employee Chat** — Employees log in with their ID and PIN and ask anything: leave balances, salary details, benefits coverage, performance review dates, bonus targets, company policies, or training resources. Every response includes citations showing which HR documents were used.
- **Admin Console** — HR administrators upload documents, manage the knowledge base, trigger re-indexing, and monitor system health — no code required.

---

## Architecture

The backend is a five-agent pipeline:

| Agent | Responsibility |
|---|---|
| Query Agent | Classifies intent, detects keywords, determines whether personal employee data is needed |
| Retrieval Agent | Searches the FAISS vector index, applies keyword reranking, groups results by source type |
| Context Builder | Assembles text, video metadata, and link chunks into a single LLM-ready context block |
| Answer Agent | Sends context and employee data to Ollama, falls back to structured mock if Ollama is offline |
| Source Agent | Builds deduplicated citations with relevance scores from retrieved chunks |

All five agents run synchronously inside a worker thread, keeping the FastAPI event loop free.

---

## System Requirements

| Requirement | Detail |
|---|---|
| Python | 3.10 or higher |
| MySQL | 8.0 or higher |
| RAM | 4 GB minimum. 8 GB recommended when running Ollama |
| OS | Windows 10/11, macOS, or Linux |
| Ollama | Optional. Required for full AI responses. Without it, the system uses structured mock responses |

---

## Installation

### Step 1 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

Packages installed:

- `faiss-cpu` — vector search index
- `sentence-transformers` — local embedding model (all-MiniLM-L6-v2)
- `fastapi` and `uvicorn` — web framework and server
- `httpx` — HTTP client for Ollama communication
- `pypdf` and `python-docx` — document parsing
- `mysql-connector-python` — MySQL database connectivity

---

### Step 2 — Configure MySQL

Open MySQL Workbench or any MySQL client as root and run the following once:

```sql
CREATE DATABASE stafflyx_hr;

DROP USER IF EXISTS 'stafflyx_user'@'localhost';
DROP USER IF EXISTS 'stafflyx_user'@'127.0.0.1';
DROP USER IF EXISTS 'stafflyx_user'@'%';

CREATE USER 'stafflyx_user'@'%' IDENTIFIED WITH mysql_native_password BY 'stafflyx_pass';
GRANT ALL PRIVILEGES ON stafflyx_hr.* TO 'stafflyx_user'@'%';
FLUSH PRIVILEGES;
```

> **Important:** The user must be created with `mysql_native_password`. MySQL 8 defaults to `caching_sha2_password`, which causes the Python connector to hang silently on Windows.

---

### Step 3 — Seed the Database

```bash
python -m database.setup_mysql
```

This creates all tables and inserts the five demo employees. On success, the script prints a credentials table confirming all records were inserted.

---

### Step 4 — Index the Knowledge Base

```bash
python -m scripts.setup_and_seed
```

This checks dependencies, verifies Ollama availability, creates required directories, and runs a full FAISS index of all documents in the `knowledge_base` folder. Safe to re-run at any time.

---

### Step 5 — Install Ollama (Optional but Recommended)

Without Ollama, the system returns structured mock responses. To enable full AI responses:

1. Download and install Ollama from [https://ollama.com](https://ollama.com)
2. Pull the model:
```bash
ollama pull mistral
```
3. Start the server:
```bash
ollama serve
```

---

## Running the Application

### Launch Both Interfaces (Recommended)

```bash
python -m scripts.launch_all
```

This starts both servers as separate subprocesses with automatic restart on crash.

| Interface | URL |
|---|---|
| Employee Chat | http://localhost:7861 |
| Admin Console | http://localhost:7860 |

### Launch Individually

```bash
# Admin console
python -m uvicorn frontend.admin_ui.admin_app:app --port 7860

# Employee chat
python -m uvicorn frontend.user_ui.user_app:app --port 7861
```

---

## Demo Credentials

### Employee Login — http://localhost:7861

| Employee ID | PIN | Name | Department |
|---|---|---|---|
| EMP001 | 1234 | Sarah Mitchell | Product |
| EMP002 | 5678 | Daniel Reyes | Engineering |
| EMP003 | 9012 | Priya Shah | Engineering |
| EMP004 | 3456 | Marcus Thompson | Human Resources |
| EMP005 | 7890 | Aisha Patel | Finance |

### Admin Login — http://localhost:7860

| Field | Value |
|---|---|
| Username | admin |
| Password | stafflyx@admin2024 |

Admin credentials can be changed by setting the `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables before starting the server.

---

## Configuration

All configuration is in `config/settings.py`. Override any value with environment variables:

| Variable | Default | Description |
|---|---|---|
| `MYSQL_HOST` | `127.0.0.1` | MySQL server address |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `stafflyx_user` | Database user |
| `MYSQL_PASSWORD` | `stafflyx_pass` | Database password |
| `MYSQL_DB` | `stafflyx_hr` | Database name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Model name |
| `ADMIN_USERNAME` | `admin` | Admin console username |
| `ADMIN_PASSWORD` | `stafflyx@admin2024` | Admin console password |

---

## Project Structure

```
stafflyx_hr_ai/
├── backend/
│   ├── agents/          # Five-agent pipeline: orchestrator, query, employee service, source, LLM
│   ├── chunking/        # Hybrid chunker for PDF, DOCX, Markdown, video, images, JSON links
│   ├── ingestion/       # Knowledge base indexing pipeline and file upload handling
│   ├── retrieval/       # FAISS query, keyword reranking, source grouping
│   ├── vector_db/       # FAISS vector store with persistence, upsert, and stats
│   └── llm/             # Ollama client with prompt templates and structured mock fallback
├── config/
│   └── settings.py      # All configuration values and environment variable overrides
├── database/
│   └── setup_mysql.py   # MySQL schema creation and demo data seeder
├── frontend/
│   ├── admin_ui/        # Admin console FastAPI app (port 7860)
│   └── user_ui/         # Employee chat FastAPI app (port 7861)
├── knowledge_base/
│   ├── policies/        # HR policy documents
│   ├── benefits/        # Benefits documentation
│   ├── training/        # Training videos and materials
│   ├── images/          # HR visual resources
│   └── links/           # External HR resource links (JSON)
├── data/
│   ├── faiss_db/        # FAISS index and metadata (auto-generated)
│   └── employee_data/   # Fallback JSON employee data if MySQL is unavailable
├── scripts/
│   ├── launch_all.py    # Starts both servers with auto-restart
│   ├── reindex.py       # CLI re-indexing tool
│   └── setup_and_seed.py # First-time setup script
└── requirements.txt
```

---

## Knowledge Base Management

The admin console at `http://localhost:7860` provides a UI for all knowledge base operations.

### CLI Re-indexing

Incremental update:
```bash
python -m scripts.reindex
```

Full reset and re-index:
```bash
python -m scripts.reindex --reset
```

### Supported File Types

| Type | Extensions |
|---|---|
| Documents | `.pdf`, `.docx`, `.md`, `.txt` |
| Videos | `.mp4`, `.avi`, `.mov`, `.mkv` (metadata indexed) |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` |
| Links | `.json` (array of URL entries with title and description) |

---

## Troubleshooting

**MySQL connection hangs silently**
The user must be created with `mysql_native_password`. MySQL 8 defaults to `caching_sha2_password`, which causes the Python connector to hang on Windows. Re-run the Step 2 SQL with the DROP/CREATE sequence to fix this.

**Access denied when connecting via 127.0.0.1**
MySQL treats `localhost` and `127.0.0.1` as different hosts. The grant uses `'%'` to cover both. If you still see access denied, verify the user was dropped and recreated with the full sequence in Step 2 and that `FLUSH PRIVILEGES` was run.

**Ollama responses are slow or time out**
The default timeout is 120 seconds. For slower machines, increase `OLLAMA_TIMEOUT` in `config/settings.py`. The mistral model requires approximately 5 GB of RAM. On lower-spec machines, try `phi3:mini` instead.

**FAISS index is empty after setup**
Check that `knowledge_base/policies`, `knowledge_base/benefits`, or `knowledge_base/training` contain files. The setup script prints a per-file chunk count — a count of zero means the file type is unsupported or the file is empty.

**Admin upload returns indexing failed**
The uploaded file type is likely unsupported, or a parsing dependency is missing. Verify `pypdf` is installed for PDF files and `python-docx` for DOCX files.

---

## Tech Stack

- **Vector Search** — FAISS (faiss-cpu)
- **Embeddings** — sentence-transformers (all-MiniLM-L6-v2, runs locally)
- **LLM** — Ollama (mistral, runs locally)
- **Database** — MySQL 8
- **Web Framework** — FastAPI + Uvicorn
- **Document Parsing** — pypdf, python-docx

---

## License

Internal use only. Not for public distribution.

---

*Stafflyx HR AI Assistant — Version 2.0*
