# 🏢 NovaCorp HR AI Assistant
### RAG-based Agentic HR Management System

> A fully local, production-grade HR AI assistant with vector search, multimodal knowledge retrieval, agentic orchestration, and a beautiful dual-interface Gradio UI — **no cloud APIs required**.

---

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Agentic Pipeline](#agentic-pipeline)
4. [Quick Start](#quick-start)
5. [Project Structure](#project-structure)
6. [Knowledge Base](#knowledge-base)
7. [Configuration](#configuration)
8. [Features](#features)
9. [Demo Accounts](#demo-accounts)
10. [Extending the System](#extending-the-system)

---

## 🎯 System Overview

NovaCorp HR AI is a **RAG (Retrieval-Augmented Generation) + Agentic** HR assistant with two interfaces:

| Interface | Audience | Port | Theme |
|-----------|----------|------|-------|
| **Admin Console** | HR Administrators | 7860 | Dark Blue |
| **Employee Chat** | All Employees | 7861 | Light Blue |

**Key capabilities:**
- 🧠 **Local LLM only** (Ollama + Mistral-7B) — no cloud APIs, no data leaves your network
- 📚 **ChromaDB vector search** — semantic retrieval over HR documents
- 🗂️ **Multimodal KB** — PDFs, DOCX, Markdown, videos, images, links
- 👤 **Personal HR data** — each employee sees their own leave, salary, and benefits
- 🤖 **5-agent pipeline** — intent classification → retrieval → context building → generation → attribution
- 📎 **Source citations** — every answer shows which documents it came from
- 🔒 **Admin-only ingestion** — employees can never modify the knowledge base

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NovaCorp HR AI System                    │
├─────────────────┬───────────────────────────────────────────┤
│   Admin UI      │            Employee UI                    │
│  (Port 7860)    │           (Port 7861)                     │
│  ┌───────────┐  │  ┌──────────────────────────────────────┐ │
│  │ Upload    │  │  │ Chat Window + Source Panel           │ │
│  │ Re-index  │  │  │ Video/Link Preview + Confidence      │ │
│  │ KB Status │  │  │ Suggested Questions                  │ │
│  └─────┬─────┘  │  └──────────────┬───────────────────────┘ │
├────────┼────────┴──────────────────┼────────────────────────┤
│        ▼                           ▼                        │
│   ┌──────────────────── Agentic Orchestrator ────────────┐  │
│   │  Agent 1: Query Understanding (Intent Classification) │  │
│   │  Agent 2: Retrieval (ChromaDB semantic search)        │  │
│   │  Agent 3: Multimodal Context Builder                  │  │
│   │  Agent 4: Answer Generation (Ollama / Mock)           │  │
│   │  Agent 5: Source Attribution                          │  │
│   └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│              ┌────────────┼────────────────┐                 │
│              ▼            ▼                ▼                 │
│        ┌─────────┐  ┌──────────┐  ┌─────────────┐          │
│        │ChromaDB │  │ Ollama   │  │Employee JSON│          │
│        │(Vectors)│  │(Mistral) │  │(Personal DB)│          │
│        └─────────┘  └──────────┘  └─────────────┘          │
│              │                                               │
│        ┌─────┴──────────────────────────────┐               │
│        │         Knowledge Base (Folders)    │               │
│        │  policies/ benefits/ training/      │               │
│        │  images/   links/                   │               │
│        └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agentic Pipeline

Every employee query flows through 5 specialized agents:

### Agent 1: Query Understanding Agent
- Classifies intent: `leave | salary | incentives | benefits | training | performance | policy | general`
- Detects if personal data is needed (first-person queries)
- Suggests KB category filter for targeted retrieval

### Agent 2: Retrieval Agent
- Embeds query using `all-MiniLM-L6-v2` (local, CPU-compatible)
- Queries ChromaDB with cosine similarity
- Retrieves top-8 candidates with similarity scores

### Agent 3: Multimodal Context Builder
- Separates results by type: text docs | videos | images | links
- Builds LLM context from text chunks
- Appends structured media metadata for UI display

### Agent 4: Answer Generation Agent
- Calls Ollama (Mistral-7B) with system prompt + employee context + KB context
- Falls back to structured mock responses if Ollama is offline
- Includes personal employee data when relevant

### Agent 5: Source Attribution Agent
- Deduplicates sources by filename
- Builds citations with relevance scores, icons, URLs, and excerpts
- Returns structured source list for UI rendering

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- pip

### 1. Clone / Download
```bash
cd hr_rag_agent
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional but Recommended) Enable Full AI
```bash
# Install Ollama from https://ollama.com
ollama pull mistral
ollama serve
```
> Without Ollama, the system runs in **mock mode** — structured, helpful demo responses based on the query type and employee data. Perfect for client demos.

### 4. Initialize the System
```bash
python scripts/setup_and_seed.py
```
This will:
- Verify dependencies
- Create all directories
- Index all seed knowledge base documents into ChromaDB

### 5. Launch
```bash
# Launch both interfaces:
python scripts/launch_all.py

# Or separately:
python frontend/admin_ui/admin_app.py    # → http://localhost:7860
python frontend/user_ui/user_app.py     # → http://localhost:7861
```

---

## 📁 Project Structure

```
hr_rag_agent/
├── config/
│   ├── settings.py              # All system configuration
│   └── __init__.py
│
├── backend/
│   ├── ingestion/
│   │   └── pipeline.py          # File upload, KB scanning, index orchestration
│   ├── chunking/
│   │   └── chunker.py           # Hybrid chunker: PDF, DOCX, MD, video, image, links
│   ├── retrieval/
│   │   └── retriever.py         # ChromaDB query + reranking + grouping
│   ├── agents/
│   │   ├── orchestrator.py      # Main 5-agent pipeline controller
│   │   ├── query_agent.py       # Intent classification agent
│   │   ├── source_agent.py      # Source attribution agent
│   │   └── employee_service.py  # Employee auth + personal data
│   ├── llm/
│   │   └── ollama_client.py     # Ollama wrapper + prompt templates + mock fallback
│   └── vector_db/
│       └── chroma_store.py      # ChromaDB manager with SentenceTransformer embeddings
│
├── frontend/
│   ├── admin_ui/
│   │   └── admin_app.py         # Gradio Admin Console (dark blue)
│   └── user_ui/
│       └── user_app.py          # Gradio Employee Chat (light blue)
│
├── knowledge_base/              # Folder-based HR content (admin uploads here)
│   ├── policies/
│   │   ├── leave_policy.md
│   │   ├── compensation_policy.md
│   │   ├── code_of_conduct.md
│   │   └── performance_policy.md
│   ├── benefits/
│   │   └── benefits_guide.md
│   ├── training/
│   │   └── training_videos.json
│   ├── images/                  # Upload org charts, flow diagrams, etc.
│   └── links/
│       └── hr_links.json
│
├── data/
│   ├── employee_data/
│   │   └── employees.json       # Mock employee personal data
│   └── chroma_db/               # ChromaDB persistent store (auto-created)
│
├── scripts/
│   ├── setup_and_seed.py        # One-time initialization
│   ├── launch_all.py            # Launch both UIs concurrently
│   └── reindex.py               # CLI re-indexing tool
│
├── requirements.txt
└── README.md
```

---

## 📚 Knowledge Base

### Adding Content (Admin)
1. Open Admin Console → http://localhost:7860
2. Login with admin credentials
3. Go to **Upload Content** tab
4. Select category, upload file(s)
5. Files are automatically chunked and indexed

### Supported Formats

| Type | Extensions | Chunking Strategy |
|------|-----------|-------------------|
| Documents | `.pdf`, `.docx`, `.md`, `.txt` | Semantic (sentence-aware, 600 token target, 13% overlap) |
| Videos | `.mp4`, `.avi`, `.mov` | Metadata + topic chunking (1 chunk per video) |
| Images | `.png`, `.jpg`, `.jpeg` | Caption/metadata chunking |
| Links | `.json` | URL metadata (1 chunk per link) |

### Chunk Metadata Schema
Every chunk stored in ChromaDB has:
```json
{
  "source_type": "pdf | docx | markdown | video | image | link",
  "file_name": "leave_policy.md",
  "file_path": "/path/to/file",
  "category": "policies | benefits | training | images | links",
  "admin_uploaded": true,
  "timestamp": "2024-01-15T10:30:00",
  "url": "https://...",
  "chunk_index": 3
}
```

---

## ⚙️ Configuration

All settings in `config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OLLAMA_MODEL` | `mistral` | Local LLM model name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformers model |
| `CHUNK_SIZE` | `600` | Target chunk size in tokens |
| `CHUNK_OVERLAP` | `80` | Overlap between chunks (~13%) |
| `RETRIEVAL_TOP_K` | `8` | Candidates fetched from ChromaDB |
| `RERANK_TOP_N` | `4` | Results after reranking |
| `SIMILARITY_THRESHOLD` | `0.25` | Min cosine similarity to include |
| `ADMIN_USERNAME` | `admin` | Admin login username |
| `ADMIN_PASSWORD` | `novacorp@admin2024` | Admin login password |

Override with environment variables:
```bash
export OLLAMA_MODEL=llama3
export ADMIN_PASSWORD=my_secure_password
```

### Switching LLM Models
```bash
# Mistral (default, recommended for HR)
ollama pull mistral

# Llama 3 8B (strong reasoning)
ollama pull llama3

# Phi-3 Mini (fastest, lightweight)
ollama pull phi3

# Gemma 7B
ollama pull gemma:7b
```
Then set `OLLAMA_MODEL` in `config/settings.py` or via environment variable.

---

## 👤 Demo Accounts

### Admin
| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `novacorp@admin2024` |

### Employees
| Employee ID | PIN | Name | Department |
|-------------|-----|------|------------|
| EMP001 | 1234 | Alice Johnson | Engineering |
| EMP002 | 5678 | Brian Martinez | Marketing |
| EMP003 | 9012 | Carol White | HR |

---

## 🔧 Extending the System

### Add a New Document Type
1. Add the extension to `SUPPORTED_*_TYPES` in `config/settings.py`
2. Add a chunker function in `backend/chunking/chunker.py`
3. Add dispatch case in `chunk_file()` dispatcher

### Add a New Intent
1. Add pattern list to `INTENT_PATTERNS` in `backend/agents/query_agent.py`
2. Add category hint to `CATEGORY_HINT`
3. Add mock response branch in `backend/llm/ollama_client.py`

### Add More Employees
Edit `data/employee_data/employees.json` following the existing schema.

### Use a Different Embedding Model
Change `EMBEDDING_MODEL` in `config/settings.py`. Reset ChromaDB after:
```bash
python scripts/reindex.py --reset
```

### Enable Cross-Encoder Reranking
In `backend/retrieval/retriever.py`, replace the keyword-boost reranker in `rerank()` with:
```python
from sentence_transformers import CrossEncoder
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = cross_encoder.predict([(query, chunk["text"]) for chunk in results])
```

---

## 🛡️ Security Notes

- Admin and employee passwords are stored in config (plaintext for demo)
- For production: use hashed passwords + environment variables
- ChromaDB data is stored locally — no external network calls
- Ollama runs fully locally — queries never leave the machine

---

## 📞 Support

For system issues, contact your IT Administrator.
For HR questions, use the Employee Chat interface or contact hr@novacorp.com

---

*NovaCorp HR AI Assistant v1.0 | Built with ChromaDB + SentenceTransformers + Gradio + Ollama*
