"""
NovaCorp HR AI Assistant - System Configuration
"""
import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
VECTOR_DB_DIR = BASE_DIR / "data" / "faiss_db"
EMPLOYEE_DATA_DIR = BASE_DIR / "data" / "employee_data"

KB_CATEGORIES = {
    "policies": KNOWLEDGE_BASE_DIR / "policies",
    "benefits":  KNOWLEDGE_BASE_DIR / "benefits",
    "training":  KNOWLEDGE_BASE_DIR / "training",
    "images":    KNOWLEDGE_BASE_DIR / "images",
    "links":     KNOWLEDGE_BASE_DIR / "links",
}

# ─── MySQL Configuration ──────────────────────────────────────────────────────
MYSQL_HOST      = os.getenv("MYSQL_HOST",     "127.0.0.1")
MYSQL_PORT      = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER      = os.getenv("MYSQL_USER",     "novacorp_user")
MYSQL_PASSWORD  = os.getenv("MYSQL_PASSWORD", "novacorp_pass")
MYSQL_DATABASE  = os.getenv("MYSQL_DB",       "novacorp_hr")
MYSQL_AUTH_PLUGIN = "mysql_native_password"

# ─── LLM (Ollama) ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "mistral")
OLLAMA_TIMEOUT  = 120
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS  = 1024

# ─── Embeddings ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL     = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# ─── FAISS ────────────────────────────────────────────────────────────────────
FAISS_INDEX_PATH = VECTOR_DB_DIR / "faiss_index.bin"
FAISS_META_PATH  = VECTOR_DB_DIR / "faiss_meta.pkl"

# ─── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 600
CHUNK_OVERLAP = 80
CHUNK_MIN_SIZE = 100

# ─── Retrieval ────────────────────────────────────────────────────────────────
RETRIEVAL_TOP_K      = 8
RERANK_TOP_N         = 4
SIMILARITY_THRESHOLD = 0.25

# ─── Auth ─────────────────────────────────────────────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "novacorp@admin2024")

# ─── Supported file types ─────────────────────────────────────────────────────
SUPPORTED_DOC_TYPES   = [".pdf", ".docx", ".md", ".txt"]
SUPPORTED_VIDEO_TYPES = [".mp4", ".avi", ".mov", ".mkv"]
SUPPORTED_IMAGE_TYPES = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
SUPPORTED_LINK_FILES  = [".json"]

# ─── Company ──────────────────────────────────────────────────────────────────
COMPANY_NAME    = "Stafflyx"
COMPANY_TAGLINE = "Intelligent HR at Your Fingertips"
HR_EMAIL        = "hr@stafflyx.com"
HR_PHONE        = "ext. 4000"
HR_PORTAL       = "hr.stafflyx.com"

# ─── Session Memory ───────────────────────────────────────────────────────────
SESSION_SUMMARY_TTL_DAYS = 30
