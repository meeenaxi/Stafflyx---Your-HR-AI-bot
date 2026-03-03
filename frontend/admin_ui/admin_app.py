"""
Stafflyx HR AI - Admin Console (FastAPI)
Full admin panel: Dashboard, Employee Management (MySQL), Chat Logs/Analytics,
Knowledge Base Management, Re-Index, System Status.
Professional dark-navy design. Zero emojis.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import logging
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config.settings import ADMIN_USERNAME, ADMIN_PASSWORD, COMPANY_NAME, KB_CATEGORIES
from backend.ingestion.pipeline import ingest_all, ingest_uploaded_file, get_kb_overview
from backend.vector_db.chroma_store import get_vector_store
from backend.llm.ollama_client import check_ollama_available
from backend.agents.employee_service import get_employee_list, get_employee_by_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"{COMPANY_NAME} HR Admin")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_admin_sessions: dict = {}

# In-memory chat log for analytics (session-scoped — replace with DB table for production)
_chat_log: list = []


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>__CN__ HR Admin Console</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#0f0c2e;--nav:#1C1678;--panel:#150f3a;--card2:#1C1678;
  --accent:#8576FF;--accent2:#6a5edf;--light:#7BC9FF;--lighter:#A3FFD6;
  --text:#e2e8f0;--muted:#8b8fc7;--border:#2a2060;
  --success:#A3FFD6;--warn:#f59e0b;--danger:#ef4444;
  --radius:10px;--shadow:0 2px 12px rgba(0,0,0,.4);
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif}
body{background:var(--bg);min-height:100vh;color:var(--text)}
.shell{display:flex;min-height:100vh}

/* ── Sidebar ── */
.sidebar{width:230px;flex-shrink:0;background:var(--nav);border-right:1px solid var(--border);display:flex;flex-direction:column}
.sb-logo{padding:20px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.sb-logo-mark{width:36px;height:36px;border-radius:8px;background:var(--accent);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sb-logo-mark svg{width:20px;height:20px;stroke:#fff;fill:none;stroke-width:2}
.sb-logo-name{font-size:.9rem;font-weight:700;color:var(--text);line-height:1.2}
.sb-logo-sub{font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}
.sb-section{padding:14px 14px 4px;font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.nav-item{display:flex;align-items:center;gap:9px;padding:9px 12px;margin:1px 6px;border-radius:7px;cursor:pointer;font-size:.84rem;color:var(--muted);transition:all .15s;user-select:none}
.nav-item svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:1.8;flex-shrink:0}
.nav-item:hover{background:rgba(133,118,255,.12);color:var(--lighter)}
.nav-item.active{background:rgba(133,118,255,.2);color:var(--light);font-weight:500}
.sb-footer{margin-top:auto;padding:14px;border-top:1px solid var(--border)}
.sb-admin-badge{font-size:.73rem;color:var(--muted);display:flex;align-items:center;gap:6px;margin-bottom:10px}
.green-dot{width:6px;height:6px;background:var(--success);border-radius:50%;flex-shrink:0}

/* ── Main ── */
.main{flex:1;overflow-y:auto;padding:24px 28px;background:var(--bg)}
.page{display:none}.page.active{display:block}
.page-hd{margin-bottom:20px}
.page-title{font-size:1.15rem;font-weight:700;color:var(--text)}
.page-sub{font-size:.82rem;color:var(--muted);margin-top:3px}

/* ── Cards ── */
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.card-hd{font-size:.73rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:14px}

/* ── Stats row ── */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:18px 16px}
.stat-val{font-size:1.7rem;font-weight:700;color:var(--light);margin-bottom:2px;font-variant-numeric:tabular-nums}
.stat-lbl{font-size:.74rem;color:var(--muted)}

/* ── Grid ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.three-col{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:900px){.two-col,.three-col,.stats-row{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.two-col,.three-col,.stats-row{grid-template-columns:1fr}}

/* ── Table ── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{background:rgba(133,118,255,.15);color:var(--lighter);padding:9px 12px;text-align:left;font-weight:600;white-space:nowrap}
td{padding:9px 12px;border-top:1px solid var(--border);color:var(--text);vertical-align:middle}
tr:hover td{background:rgba(133,118,255,.05)}
.mono{font-family:'JetBrains Mono',monospace;font-size:.78em;color:var(--lighter);background:rgba(133,118,255,.12);padding:2px 6px;border-radius:4px}

/* ── Buttons ── */
.btn{padding:9px 18px;border-radius:7px;font-size:.84rem;font-weight:600;cursor:pointer;border:none;transition:all .2s;font-family:'Inter',sans-serif}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2);transform:translateY(-1px);box-shadow:0 4px 14px rgba(133,118,255,.4)}
.btn-secondary{background:transparent;border:1px solid var(--border);color:var(--lighter)}
.btn-secondary:hover{background:rgba(133,118,255,.1)}
.btn-sm{padding:4px 10px;font-size:.75rem}
.btn-danger{background:transparent;border:1px solid var(--danger);color:var(--danger)}
.btn-danger:hover{background:rgba(239,68,68,.1)}

/* ── Forms ── */
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:.71rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:5px}
.form-group input,.form-group select,.form-group textarea{
  width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:7px;
  font-size:.87rem;background:rgba(255,255,255,.04);color:var(--text);
  outline:none;font-family:'Inter',sans-serif;
}
.form-group input:focus,.form-group textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(133,118,255,.15)}
.form-group select option{background:var(--panel)}

/* ── Upload zone ── */
.upload-zone{border:2px dashed var(--border);border-radius:var(--radius);padding:26px;text-align:center;cursor:pointer;transition:all .2s}
.upload-zone:hover{border-color:var(--accent);background:rgba(133,118,255,.05)}
.upload-zone svg{width:34px;height:34px;stroke:var(--muted);fill:none;stroke-width:1.5;margin-bottom:8px}
.upload-zone p{color:var(--muted);font-size:.84rem;margin-top:4px}
.upload-zone p.hint{font-size:.74rem}

/* ── Result box ── */
.result-box{
  margin-top:12px;padding:12px 14px;background:rgba(0,0,0,.35);
  border:1px solid var(--border);border-radius:7px;
  font-size:.8rem;line-height:1.7;white-space:pre-wrap;
  max-height:260px;overflow-y:auto;
  font-family:'JetBrains Mono',monospace;color:var(--lighter);
}

/* ── Badges ── */
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:20px;font-size:.72rem;font-weight:600}
.b-green{background:rgba(163,255,214,.15);color:#A3FFD6}
.b-red{background:rgba(239,68,68,.15);color:#f87171}
.b-yellow{background:rgba(245,158,11,.15);color:#fbbf24}
.b-blue{background:rgba(133,118,255,.2);color:var(--lighter)}
.b-gray{background:rgba(100,116,139,.15);color:var(--muted)}

/* ── Status item ── */
.status-item{background:var(--card2);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px}
.status-item-hd{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.status-item-name{font-size:.86rem;font-weight:600;color:var(--text)}
.status-item-msg{font-size:.78rem;color:var(--muted);padding-left:20px}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot-green{background:var(--success)}
.dot-red{background:var(--danger)}
.dot-yellow{background:var(--warn)}

/* ── Health list ── */
.health-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);font-size:.83rem}
.health-row:last-child{border:none}
.health-lbl{font-weight:500;color:var(--text);min-width:150px}
.health-val{color:var(--muted)}

/* ── Info box ── */
.info-box{background:var(--card2);border:1px solid var(--border);border-radius:var(--radius);padding:14px;font-size:.83rem;line-height:1.8}
.info-box b{color:var(--lighter)}

/* ── Warning box ── */
.warn-box{background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.3);border-radius:7px;padding:12px 14px;font-size:.82rem;color:var(--warn);margin-bottom:14px}

/* ── Employee detail grid ── */
.detail-section{margin-bottom:16px}
.detail-section-title{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--accent);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.detail-item{background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:7px;padding:9px 11px}
.detail-key{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px}
.detail-val{font-size:.86rem;color:var(--text);font-weight:500}

/* ── Modal ── */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.65);display:none;align-items:center;justify-content:center;z-index:100;padding:16px}
.modal-overlay.open{display:flex}
.modal{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:24px;max-width:640px;width:100%;max-height:85vh;overflow-y:auto}
.modal-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.modal-title{font-size:1rem;font-weight:700;color:var(--text)}
.modal-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:1.3rem;padding:2px 8px;border-radius:5px}
.modal-close:hover{background:rgba(255,255,255,.07);color:var(--text)}

/* ── Login overlay ── */
#login-overlay{position:fixed;inset:0;background:var(--bg);display:flex;align-items:center;justify-content:center;z-index:200}
.login-box{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:32px;width:380px;box-shadow:var(--shadow)}
.login-title{font-size:1.15rem;font-weight:700;color:var(--text);margin-bottom:4px}
.login-sub{font-size:.82rem;color:var(--muted);margin-bottom:22px;line-height:1.5}
.error-msg{color:var(--danger);font-size:.81rem;margin-top:8px;min-height:16px}

/* ── Progress bar (intent chart) ── */
.bar-row{margin-bottom:8px}
.bar-label{display:flex;justify-content:space-between;font-size:.79rem;color:var(--text);margin-bottom:3px}
.bar-track{height:6px;background:rgba(255,255,255,.06);border-radius:3px}
.bar-fill{height:6px;background:var(--accent);border-radius:3px;transition:width .4s}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:rgba(133,118,255,.4);border-radius:3px}
</style>
</head>
<body>

<!-- Login Overlay -->
<div id="login-overlay">
  <div class="login-box">
    <div class="login-title">Admin Console</div>
    <div class="login-sub">Sign in with your administrator credentials to manage the Stafflyx HR AI system.</div>
    <div class="form-group"><label>Username</label><input id="adm-user" placeholder="admin" autocomplete="username"/></div>
    <div class="form-group"><label>Password</label><input id="adm-pass" type="password" placeholder="Password" autocomplete="current-password"/></div>
    <button class="btn btn-primary" id="login-btn" onclick="doLogin()" style="width:100%">Sign In</button>
    <div class="error-msg" id="login-err"></div>
  </div>
</div>

<!-- App Shell -->
<div class="shell">

  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sb-logo">
      <div class="sb-logo-mark">
        <svg viewBox="0 0 24 24"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
      </div>
      <div>
        <div class="sb-logo-name">__CN__</div>
        <div class="sb-logo-sub">HR Admin</div>
      </div>
    </div>

    <div class="sb-section">Overview</div>
    <div class="nav-item active" data-page="dashboard">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
      Dashboard
    </div>

    <div class="sb-section">People</div>
    <div class="nav-item" data-page="employees">
      <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>
      Employees
    </div>
    <div class="nav-item" data-page="chatlogs">
      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
      Chat Logs
    </div>

    <div class="sb-section">Knowledge Base</div>
    <div class="nav-item" data-page="upload">
      <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      Upload Content
    </div>
    <div class="nav-item" data-page="kb">
      <svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
      Knowledge Base
    </div>
    <div class="nav-item" data-page="reindex">
      <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
      Re-Index
    </div>

    <div class="sb-section">System</div>
    <div class="nav-item" data-page="status">
      <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      System Status
    </div>

    <div class="sb-footer">
      <div class="sb-admin-badge"><span class="green-dot"></span>Admin Session Active</div>
      <button class="btn btn-secondary" onclick="doLogout()" style="width:100%;font-size:.78rem;padding:7px 12px">Sign Out</button>
    </div>
  </div>

  <!-- Main Content -->
  <div class="main">

    <!-- DASHBOARD -->
    <div class="page active" id="page-dashboard">
      <div class="page-hd">
        <div class="page-title">Dashboard</div>
        <div class="page-sub">System overview for the Stafflyx HR AI platform.</div>
      </div>
      <div class="stats-row">
        <div class="stat"><div class="stat-val" id="stat-emp">-</div><div class="stat-lbl">Total Employees</div></div>
        <div class="stat"><div class="stat-val" id="stat-chunks">-</div><div class="stat-lbl">KB Chunks Indexed</div></div>
        <div class="stat"><div class="stat-val" id="stat-chats">-</div><div class="stat-lbl">Chats This Session</div></div>
        <div class="stat"><div class="stat-val" id="stat-ai" style="font-size:1rem;padding-top:4px">-</div><div class="stat-lbl">AI Engine</div></div>
      </div>
      <div class="two-col">
        <div class="card">
          <div class="card-hd">System Health</div>
          <div id="dash-health"><div style="color:var(--muted);font-size:.83rem">Loading...</div></div>
        </div>
        <div class="card">
          <div class="card-hd">Top Question Topics</div>
          <div id="dash-topics"><div style="color:var(--muted);font-size:.83rem">No sessions recorded yet.</div></div>
        </div>
      </div>
    </div>

    <!-- EMPLOYEES -->
    <div class="page" id="page-employees">
      <div class="page-hd">
        <div class="page-title">Employee Management</div>
        <div class="page-sub">All employee records sourced directly from MySQL. Click any row to view full HR data.</div>
      </div>
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <div class="card-hd" style="margin:0">All Employees</div>
          <button class="btn btn-secondary btn-sm" onclick="loadEmployees()">Refresh</button>
        </div>
        <div class="tbl-wrap" id="emp-table-wrap">
          <div style="color:var(--muted);font-size:.83rem;padding:8px 0">Click Refresh to load employee data from MySQL.</div>
        </div>
      </div>
    </div>

    <!-- CHAT LOGS -->
    <div class="page" id="page-chatlogs">
      <div class="page-hd">
        <div class="page-title">Chat Logs &amp; Analytics</div>
        <div class="page-sub">Session-level analytics. Full persistence requires connecting the chat log to MySQL (see README).</div>
      </div>
      <div class="two-col" style="margin-bottom:16px">
        <div class="card">
          <div class="card-hd">Intent Distribution</div>
          <div id="intent-dist"><div style="color:var(--muted);font-size:.83rem">No chat data yet.</div></div>
        </div>
        <div class="card">
          <div class="card-hd">Recent Sessions</div>
          <div id="recent-sessions" style="color:var(--muted);font-size:.83rem">No sessions recorded.</div>
        </div>
      </div>
      <div class="card">
        <div class="card-hd">Full Chat Log (This Session)</div>
        <div class="tbl-wrap" id="chat-log-wrap">
          <div style="color:var(--muted);font-size:.83rem;padding:4px 0">No chats recorded in this session.</div>
        </div>
      </div>
    </div>

    <!-- UPLOAD -->
    <div class="page" id="page-upload">
      <div class="page-hd">
        <div class="page-title">Upload Content</div>
        <div class="page-sub">Add HR documents, training resources, and external links to the knowledge base.</div>
      </div>
      <div class="two-col">
        <div class="card">
          <div class="card-hd">Upload Files</div>
          <div class="form-group">
            <label>Category</label>
            <select id="upload-cat">__CAT_OPTIONS__</select>
          </div>
          <div class="upload-zone" onclick="document.getElementById('file-input').click()">
            <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <p>Click to select files</p>
            <p class="hint">PDF, DOCX, MD, TXT, MP4, PNG, JPG</p>
            <input id="file-input" type="file" multiple accept=".pdf,.docx,.md,.txt,.mp4,.png,.jpg,.jpeg" style="display:none" onchange="showFiles(this)"/>
          </div>
          <div id="file-list" style="margin-top:8px;font-size:.79rem;color:var(--lighter)"></div>
          <button class="btn btn-primary" style="margin-top:12px" onclick="doUpload()">Upload and Index</button>
          <div id="upload-result" class="result-box" style="display:none"></div>
        </div>
        <div>
          <div class="card" style="margin-bottom:16px">
            <div class="card-hd">Add External Link</div>
            <div class="form-group"><label>Title</label><input id="link-title" placeholder="e.g. Benefits Enrollment Portal"/></div>
            <div class="form-group"><label>URL</label><input id="link-url" placeholder="https://..."/></div>
            <div class="form-group"><label>Description</label><textarea id="link-desc" rows="2" placeholder="What is this link for?"></textarea></div>
            <div class="form-group">
              <label>Category</label>
              <select id="link-cat">
                <option value="benefits">Benefits</option>
                <option value="policies">Policies</option>
                <option value="training">Training</option>
                <option value="links" selected>Links</option>
              </select>
            </div>
            <button class="btn btn-primary" onclick="doAddLink()">Add Link</button>
            <div id="link-result" class="result-box" style="display:none"></div>
          </div>
          <div class="info-box">
            <b>Supported formats</b><br/>
            PDF documents &nbsp;|&nbsp; Word (.docx)<br/>
            Markdown (.md) &nbsp;|&nbsp; Plain text (.txt)<br/>
            MP4 videos (metadata) &nbsp;|&nbsp; Images (PNG, JPG)<br/><br/>
            <b>Categories</b><br/>
            policies &mdash; HR rules and compliance<br/>
            benefits &mdash; Benefits documentation<br/>
            training &mdash; Learning resources<br/>
            links &mdash; External HR portals
          </div>
        </div>
      </div>
    </div>

    <!-- KNOWLEDGE BASE -->
    <div class="page" id="page-kb">
      <div class="page-hd">
        <div class="page-title">Knowledge Base</div>
        <div class="page-sub">All indexed files and ChromaDB vector store statistics.</div>
      </div>
      <div class="two-col">
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <div class="card-hd" style="margin:0">Indexed Files</div>
            <button class="btn btn-secondary btn-sm" onclick="loadKB()">Refresh</button>
          </div>
          <div class="tbl-wrap" id="kb-table-wrap">
            <div style="color:var(--muted);font-size:.83rem">Click Refresh to load.</div>
          </div>
        </div>
        <div class="card">
          <div class="card-hd">Vector Store Stats</div>
          <div id="kb-stats" style="color:var(--muted);font-size:.83rem">Click Refresh to load.</div>
        </div>
      </div>
    </div>

    <!-- RE-INDEX -->
    <div class="page" id="page-reindex">
      <div class="page-hd">
        <div class="page-title">Re-Index Knowledge Base</div>
        <div class="page-sub">Scan all KB folders and rebuild the vector store from scratch.</div>
      </div>
      <div class="card" style="max-width:540px">
        <div class="warn-box">
          Reset mode will wipe all existing vectors before re-indexing. Use with caution in production.
        </div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
          <input type="checkbox" id="reset-toggle" style="width:15px;height:15px;cursor:pointer"/>
          <label for="reset-toggle" style="font-size:.85rem;cursor:pointer;color:var(--text)">Reset ChromaDB before re-indexing</label>
        </div>
        <button class="btn btn-primary" onclick="doReindex()">Start Re-Index</button>
        <div id="reindex-result" class="result-box" style="display:none"></div>
      </div>
    </div>

    <!-- SYSTEM STATUS -->
    <div class="page" id="page-status">
      <div class="page-hd">
        <div class="page-title">System Status</div>
        <div class="page-sub">Live health check for all Stafflyx HR AI components.</div>
      </div>
      <div style="margin-bottom:16px">
        <button class="btn btn-primary" onclick="checkStatus()">Run Diagnostics</button>
      </div>
      <div id="status-grid" class="three-col">
        <div style="color:var(--muted);font-size:.83rem">Click Run Diagnostics to check system health.</div>
      </div>
    </div>

  </div><!-- /main -->
</div><!-- /shell -->

<!-- Employee Detail Modal -->
<div class="modal-overlay" id="emp-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hd">
      <div class="modal-title" id="modal-emp-name">Employee Detail</div>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div id="modal-body"></div>
  </div>
</div>

<script>
let sid = null;

// ── Navigation ──────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item[data-page]').forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    item.classList.add('active');
    document.getElementById('page-' + page).classList.add('active');
    // Auto-load on navigation
    if (page === 'dashboard') loadDashboard();
    if (page === 'employees') loadEmployees();
    if (page === 'chatlogs') loadChatLogs();
    if (page === 'kb') loadKB();
    if (page === 'status') checkStatus();
  });
});

// ── Auth ────────────────────────────────────────────────────────────────────
async function doLogin() {
  const u = document.getElementById('adm-user').value.trim();
  const p = document.getElementById('adm-pass').value.trim();
  const errEl = document.getElementById('login-err');
  errEl.textContent = '';
  if (!u || !p) { errEl.textContent = 'Please enter username and password.'; return; }
  const btn = document.getElementById('login-btn');
  btn.disabled = true; btn.textContent = 'Signing in...';
  const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username:u, password:p})});
  const d = await r.json();
  btn.disabled = false; btn.textContent = 'Sign In';
  if (d.success) {
    sid = d.session_id;
    document.getElementById('login-overlay').style.display = 'none';
    loadDashboard();
  } else {
    errEl.textContent = d.error;
  }
}

async function doLogout() {
  if (sid) await fetch('/api/logout', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  sid = null;
  document.getElementById('login-overlay').style.display = 'flex';
  document.getElementById('adm-pass').value = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.getElementById('login-overlay').style.display !== 'none') doLogin();
});

// ── Dashboard ───────────────────────────────────────────────────────────────
async function loadDashboard() {
  const r = await fetch('/api/dashboard', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  const d = await r.json();
  document.getElementById('stat-emp').textContent    = d.employee_count;
  document.getElementById('stat-chunks').textContent = Number(d.chunk_count).toLocaleString();
  document.getElementById('stat-chats').textContent  = d.chat_count;
  document.getElementById('stat-ai').textContent     = d.ollama_label;
  document.getElementById('dash-health').innerHTML   = d.health_html;
  document.getElementById('dash-topics').innerHTML   = d.topics_html;
}

// ── Employees ───────────────────────────────────────────────────────────────
async function loadEmployees() {
  document.getElementById('emp-table-wrap').innerHTML = '<div style="color:var(--muted);font-size:.83rem">Loading from MySQL...</div>';
  const r = await fetch('/api/employees', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  const d = await r.json();
  if (!d.employees || d.employees.length === 0) {
    document.getElementById('emp-table-wrap').innerHTML = '<div style="color:var(--warn);font-size:.83rem;padding:8px 0">No employees found. Ensure MySQL is running and seeded with demo data.</div>';
    return;
  }
  let html = '<table><thead><tr><th>Employee ID</th><th>Name</th><th>Department</th><th>Role</th><th>Grade</th><th>Join Date</th><th></th></tr></thead><tbody>';
  d.employees.forEach(e => {
    html += `<tr>
      <td><span class="mono">${e.employee_id||''}</span></td>
      <td style="font-weight:500">${e.name||''}</td>
      <td>${e.department||'-'}</td>
      <td style="color:var(--muted)">${e.role||'-'}</td>
      <td>${e.grade||'-'}</td>
      <td style="color:var(--muted)">${e.join_date||'-'}</td>
      <td><button class="btn btn-secondary btn-sm" onclick="viewEmployee('${e.employee_id}')">View</button></td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('emp-table-wrap').innerHTML = html;
}

async function viewEmployee(empId) {
  document.getElementById('modal-emp-name').textContent = 'Loading...';
  document.getElementById('modal-body').innerHTML = '<div style="color:var(--muted);font-size:.84rem;padding:8px 0">Fetching from MySQL...</div>';
  document.getElementById('emp-modal').classList.add('open');
  const r = await fetch('/api/employee_detail', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid, employee_id:empId})});
  const d = await r.json();
  document.getElementById('modal-emp-name').textContent = d.name || empId;
  document.getElementById('modal-body').innerHTML = d.html;
}

function closeModal() {
  document.getElementById('emp-modal').classList.remove('open');
}

// ── Chat Logs ────────────────────────────────────────────────────────────────
async function loadChatLogs() {
  const r = await fetch('/api/chat_logs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  const d = await r.json();
  document.getElementById('intent-dist').innerHTML     = d.intent_html;
  document.getElementById('recent-sessions').innerHTML = d.recent_html;
  document.getElementById('chat-log-wrap').innerHTML   = d.table_html;
}

// ── KB ───────────────────────────────────────────────────────────────────────
async function loadKB() {
  const r = await fetch('/api/kb_overview', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  const d = await r.json();
  let html = '<table><thead><tr><th>Category</th><th>File</th></tr></thead><tbody>';
  (d.rows||[]).forEach(row => {
    html += `<tr><td><span class="badge b-blue">${row[0]}</span></td><td>${row[1]}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('kb-table-wrap').innerHTML = html;
  document.getElementById('kb-stats').innerHTML = d.stats_html;
}

// ── Upload ───────────────────────────────────────────────────────────────────
function showFiles(input) {
  const names = Array.from(input.files).map(f => f.name);
  document.getElementById('file-list').textContent = names.join(', ');
}

async function doUpload() {
  const cat = document.getElementById('upload-cat').value;
  const files = document.getElementById('file-input').files;
  if (!files.length) { alert('Please select one or more files first.'); return; }
  const fd = new FormData();
  fd.append('category', cat);
  fd.append('session_id', sid);
  for (const f of files) fd.append('files', f);
  const box = document.getElementById('upload-result');
  box.style.display = 'block'; box.textContent = 'Uploading and indexing...';
  const r = await fetch('/api/upload', {method:'POST', body: fd});
  const d = await r.json();
  box.textContent = d.result;
}

async function doAddLink() {
  const body = {
    session_id: sid,
    title:       document.getElementById('link-title').value,
    url:         document.getElementById('link-url').value,
    description: document.getElementById('link-desc').value,
    category:    document.getElementById('link-cat').value,
  };
  const r = await fetch('/api/add_link', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  const box = document.getElementById('link-result');
  box.style.display = 'block'; box.textContent = d.result;
}

// ── Re-Index ─────────────────────────────────────────────────────────────────
async function doReindex() {
  const reset = document.getElementById('reset-toggle').checked;
  const box = document.getElementById('reindex-result');
  box.style.display = 'block'; box.textContent = 'Re-indexing... please wait. This may take a minute.';
  const r = await fetch('/api/reindex', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid, reset})});
  const d = await r.json();
  box.textContent = d.result;
}

// ── Status ───────────────────────────────────────────────────────────────────
async function checkStatus() {
  document.getElementById('status-grid').innerHTML = '<div style="color:var(--muted);font-size:.83rem">Running diagnostics...</div>';
  const r = await fetch('/api/status', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id:sid})});
  const d = await r.json();
  document.getElementById('status-grid').innerHTML = d.html;
}
</script>
</body>
</html>
"""


def _get_html():
    cat_opts = "".join(
        f'<option value="{k}">{k.title()}</option>' for k in KB_CATEGORIES.keys()
    )
    return HTML.replace("__CN__", COMPANY_NAME).replace("__CAT_OPTIONS__", cat_opts)


def _check_auth(session_id: str):
    if not _admin_sessions.get(session_id):
        raise HTTPException(status_code=401, detail="Not authenticated")


# ── Helper: build employee detail HTML ───────────────────────────────────────

def _build_employee_detail_html(emp: dict) -> str:
    def v(val, fallback="-"):
        if val is None or val == "": return fallback
        return str(val)

    def money(val):
        try:
            return f"${float(val):,.2f}"
        except (TypeError, ValueError):
            return v(val)

    leave    = emp.get("leave", {})
    salary   = emp.get("salary", {})
    benefits = emp.get("benefits", {})
    inc      = emp.get("incentives", {})
    perf     = emp.get("performance", {})

    def section(title, items):
        cells = "".join(
            f'<div class="detail-item"><div class="detail-key">{k}</div><div class="detail-val">{v(val)}</div></div>'
            for k, val in items
        )
        return f'<div class="detail-section"><div class="detail-section-title">{title}</div><div class="detail-grid">{cells}</div></div>'

    html = section("Employee Information", [
        ("Department",  emp.get("department")),
        ("Role",        emp.get("role")),
        ("Grade",       emp.get("grade")),
        ("Manager",     emp.get("manager")),
        ("Join Date",   emp.get("join_date")),
        ("Email",       emp.get("email")),
    ])
    html += section("Leave Balances", [
        ("Annual Leave",  f"{v(leave.get('annual_remaining'))} remaining (used {v(leave.get('annual_used'))} / {v(leave.get('annual_total'))})"),
        ("Sick Leave",    f"{v(leave.get('sick_remaining'))} remaining"),
        ("Casual Leave",  f"{v(leave.get('casual_remaining'))} remaining"),
        ("Maternity",     "Available" if leave.get("maternity_available") else "Not applicable"),
    ])
    html += section("Salary", [
        ("Base Salary",      money(salary.get("base_salary"))),
        ("Currency",         v(salary.get("currency", "USD"))),
        ("Last Increment",   f"{v(salary.get('last_increment_pct'))}% on {v(salary.get('last_increment_date'))}"),
        ("Pay Frequency",    v(salary.get("pay_frequency", "Monthly"))),
    ])
    html += section("Benefits", [
        ("Health Insurance", v(benefits.get("health_insurance"))),
        ("Dental",           "Yes" if benefits.get("dental") else v(benefits.get("dental_insurance", "-"))),
        ("Vision",           "Yes" if benefits.get("vision") else v(benefits.get("vision_insurance", "-"))),
        ("401(k) Match",     f"{v(benefits.get('match_401k_pct', benefits.get('retirement_match_pct')))}%"),
        ("Learning Budget",  money(benefits.get("learning_budget"))),
        ("Gym Stipend",      money(benefits.get("gym_stipend", benefits.get("remote_work_stipend")))),
    ])
    html += section("Incentives", [
        ("Bonus Target",   f"{v(inc.get('annual_bonus_target_pct'))}% of base salary"),
        ("Stock Options",  v(inc.get("stock_options"))),
        ("Referral Bonus", money(inc.get("referral_bonus", inc.get("referral_bonus_available")))),
        ("Last Bonus Paid", money(inc.get("last_bonus_paid"))),
    ])
    html += section("Performance", [
        ("Last Review Score", f"{v(perf.get('last_review_score'))} / 5"),
        ("Last Review Date",  v(perf.get("last_review_date"))),
        ("Next Review Date",  v(perf.get("next_review_date"))),
        ("Goals Completed",   f"{v(perf.get('goals_completed'))} / {v(perf.get('goals_total'))}"),
    ])
    return html


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return _get_html()


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    if body.get("username") == ADMIN_USERNAME and body.get("password") == ADMIN_PASSWORD:
        s = str(uuid.uuid4())
        _admin_sessions[s] = True
        return JSONResponse({"success": True, "session_id": s})
    return JSONResponse({"success": False, "error": "Invalid credentials. Please try again."})


@app.post("/api/logout")
async def api_logout(request: Request):
    body = await request.json()
    _admin_sessions.pop(body.get("session_id", ""), None)
    return JSONResponse({"success": True})


@app.post("/api/dashboard")
async def api_dashboard(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))

    ollama_ok = await asyncio.to_thread(check_ollama_available)
    vs        = get_vector_store()
    stats     = await asyncio.to_thread(vs.get_stats)
    employees = await asyncio.to_thread(get_employee_list)

    # MySQL status
    mysql_ok = len(employees) > 0
    try:
        from backend.agents.employee_service import _get_mysql_conn
        conn = _get_mysql_conn(); conn.close()
        mysql_ok = True
    except Exception:
        mysql_ok = False

    health_rows = [
        ("AI Engine (Ollama)", "dot-green" if ollama_ok else "dot-yellow",
         "Online" if ollama_ok else "Offline — demo mode active"),
        ("ChromaDB Vector Store", "dot-green",
         f"Connected &mdash; {stats.get('total_chunks', 0):,} chunks indexed"),
        ("MySQL Database", "dot-green" if mysql_ok else "dot-red",
         f"Connected &mdash; {len(employees)} employees loaded" if mysql_ok else "Unavailable — check credentials"),
        ("Embedding Model", "dot-green", "all-MiniLM-L6-v2 (local)"),
        ("Knowledge Base", "dot-green",
         f"{stats.get('unique_files', 0)} files indexed across {len(KB_CATEGORIES)} categories"),
    ]
    health_html = "".join(
        f"<div class='health-row'>"
        f"<span class='dot {cls}'></span>"
        f"<span class='health-lbl'>{lbl}</span>"
        f"<span class='health-val'>{msg}</span>"
        f"</div>"
        for lbl, cls, msg in health_rows
    )

    # Top topics
    from collections import Counter
    intents = Counter(e.get("intent", "general") for e in _chat_log)
    if intents:
        max_count = max(intents.values())
        topics_html = "".join(
            f"<div class='bar-row'>"
            f"<div class='bar-label'><span>{i.replace('_',' ').title()}</span><span>{c}</span></div>"
            f"<div class='bar-track'><div class='bar-fill' style='width:{int(c/max_count*100)}%'></div></div>"
            f"</div>"
            for i, c in intents.most_common(6)
        )
    else:
        topics_html = "<div style='color:var(--muted);font-size:.83rem'>No chat sessions recorded yet.</div>"

    return JSONResponse({
        "employee_count": len(employees),
        "chunk_count":    stats.get("total_chunks", 0),
        "chat_count":     len(_chat_log),
        "ollama_label":   "Online" if ollama_ok else "Offline",
        "health_html":    health_html,
        "topics_html":    topics_html,
    })


@app.post("/api/employees")
async def api_employees(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))
    employees = await asyncio.to_thread(get_employee_list)
    return JSONResponse({"employees": employees})


@app.post("/api/employee_detail")
async def api_employee_detail(request: Request):
    body   = await request.json()
    _check_auth(body.get("session_id", ""))
    emp_id = body.get("employee_id", "")
    emp    = await asyncio.to_thread(get_employee_by_id, emp_id)
    if not emp:
        return JSONResponse({
            "name": emp_id,
            "html": "<div style='color:var(--warn);font-size:.84rem'>Employee not found in MySQL. Ensure the database is seeded.</div>"
        })
    return JSONResponse({
        "name": emp.get("name", emp_id),
        "html": _build_employee_detail_html(emp)
    })


@app.post("/api/chat_logs")
async def api_chat_logs(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))

    from collections import Counter
    intents = Counter(e.get("intent", "general") for e in _chat_log)

    if intents:
        max_count = max(intents.values())
        intent_html = "".join(
            f"<div class='bar-row'>"
            f"<div class='bar-label'><span>{i.replace('_',' ').title()}</span><span>{c}</span></div>"
            f"<div class='bar-track'><div class='bar-fill' style='width:{int(c/max_count*100)}%'></div></div>"
            f"</div>"
            for i, c in intents.most_common(8)
        )
    else:
        intent_html = "<div style='color:var(--muted);font-size:.83rem'>No data yet.</div>"

    recent = _chat_log[-5:][::-1]
    if recent:
        recent_html = "".join(
            f"<div style='margin-bottom:8px;font-size:.82rem'>"
            f"<span style='color:var(--lighter);font-weight:500'>{e.get('employee_id','?')}</span>"
            f" &mdash; <span class='badge b-blue'>{e.get('intent','?')}</span>"
            f"<div style='color:var(--muted);margin-top:2px'>{e.get('query','')[:80]}...</div>"
            f"</div>"
            for e in recent
        )
    else:
        recent_html = "<div style='color:var(--muted);font-size:.83rem'>No sessions yet.</div>"

    if _chat_log:
        table_html = (
            "<table><thead><tr><th>#</th><th>Employee</th><th>Intent</th><th>Confidence</th><th>Query</th><th>Source</th></tr></thead><tbody>"
            + "".join(
                f"<tr>"
                f"<td style='color:var(--muted)'>{i+1}</td>"
                f"<td><span class='mono'>{e.get('employee_id','?')}</span></td>"
                f"<td><span class='badge b-blue'>{e.get('intent','?')}</span></td>"
                f"<td>{int(float(e.get('confidence',0))*100)}%</td>"
                f"<td style='max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{e.get('query','')[:80]}</td>"
                f"<td style='color:var(--muted);font-size:.78rem'>{e.get('model','?')}</td>"
                f"</tr>"
                for i, e in enumerate(_chat_log)
            )
            + "</tbody></table>"
        )
    else:
        table_html = "<div style='color:var(--muted);font-size:.83rem;padding:4px 0'>No chats recorded in this session.</div>"

    return JSONResponse({
        "intent_html": intent_html,
        "recent_html": recent_html,
        "table_html":  table_html,
    })


@app.post("/api/upload")
async def api_upload(
    files: list[UploadFile] = File(...),
    category: str = Form(...),
    session_id: str = Form(...)
):
    _check_auth(session_id)
    results = []
    for f in files:
        file_bytes = await f.read()
        try:
            result = await asyncio.to_thread(ingest_uploaded_file, file_bytes, f.filename, category)
            results.append(f"OK  {f.filename} -> {result['chunks_indexed']} chunks indexed in '{category}'")
        except Exception as e:
            results.append(f"ERR {f.filename} -> {e}")
    return JSONResponse({"result": "\n".join(results)})


@app.post("/api/add_link")
async def api_add_link(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))
    url = body.get("url", "")
    if not url.startswith("http"):
        return JSONResponse({"result": "Please enter a valid URL starting with http:// or https://"})
    links_file = KB_CATEGORIES["links"] / "hr_links.json"
    try:
        existing = json.loads(links_file.read_text()) if links_file.exists() else []
    except Exception:
        existing = []
    new_entry = {
        "title":       body.get("title") or url,
        "url":         url,
        "description": body.get("description", ""),
        "category":    body.get("category", "links"),
        "tags":        [body.get("category", "links")]
    }
    existing.append(new_entry)
    links_file.write_text(json.dumps(existing, indent=2))
    try:
        await asyncio.to_thread(ingest_uploaded_file, links_file.read_bytes(), links_file.name, "links")
        return JSONResponse({"result": f"Link added and indexed: {new_entry['title']}"})
    except Exception as e:
        return JSONResponse({"result": f"Link saved but indexing failed: {e}"})


@app.post("/api/kb_overview")
async def api_kb_overview(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))
    overview = await asyncio.to_thread(get_kb_overview)
    vs_stats = overview["vector_stats"]
    rows = []
    for cat, files in overview["kb_files"].items():
        for f in files:
            rows.append([cat.title(), f])
    if not rows:
        rows = [["—", "No files uploaded yet"]]
    stats_html = (
        f"<div class='info-box'>"
        f"<b>Total Chunks:</b> {vs_stats.get('total_chunks', 0):,}<br/>"
        f"<b>Unique Files:</b> {vs_stats.get('unique_files', 0)}<br/>"
        f"<b>Source Types:</b> {json.dumps(vs_stats.get('source_types', {}))}<br/>"
        f"<b>Categories:</b> {json.dumps(vs_stats.get('categories', {}))}"
        f"</div>"
    )
    return JSONResponse({"rows": rows, "stats_html": stats_html})


@app.post("/api/reindex")
async def api_reindex(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))
    reset = body.get("reset", False)
    try:
        result = await asyncio.to_thread(ingest_all, reset)
        lines = [
            "Re-index Complete",
            f"Files processed : {result['total_files']}",
            f"Chunks indexed  : {result['total_chunks']:,}",
            "",
            "File Results:"
        ]
        for r in result["results"]:
            status = "OK " if r["status"] == "ok" else "ERR"
            lines.append(f"{status}  {r['file']} ({r['category']}) -> {r['chunks']} chunks")
        return JSONResponse({"result": "\n".join(lines)})
    except Exception as e:
        return JSONResponse({"result": f"Re-index failed: {e}"})


@app.post("/api/status")
async def api_status(request: Request):
    body = await request.json()
    _check_auth(body.get("session_id", ""))

    ollama_ok = await asyncio.to_thread(check_ollama_available)
    vs    = get_vector_store()
    stats = await asyncio.to_thread(vs.get_stats)

    mysql_ok  = False
    mysql_msg = "Unavailable"
    try:
        from backend.agents.employee_service import _get_mysql_conn
        conn = _get_mysql_conn(); conn.close()
        mysql_ok  = True
        emps      = await asyncio.to_thread(get_employee_list)
        mysql_msg = f"Connected &mdash; {len(emps)} employees"
    except Exception as e:
        mysql_msg = f"Error: {e}"

    items = [
        ("AI Engine (Ollama)", "dot-green" if ollama_ok else "dot-yellow",
         "Online" if ollama_ok else "Offline &mdash; demo mode active"),
        ("ChromaDB", "dot-green",
         f"Connected &mdash; {stats.get('total_chunks', 0):,} chunks"),
        ("MySQL Database", "dot-green" if mysql_ok else "dot-red", mysql_msg),
        ("Embedding Model", "dot-green", "all-MiniLM-L6-v2 (local)"),
        ("Knowledge Base", "dot-green",
         f"{stats.get('unique_files', 0)} files across {len(KB_CATEGORIES)} categories"),
        ("Admin Session", "dot-green", "Active"),
    ]
    html = "".join(
        f"<div class='status-item'>"
        f"<div class='status-item-hd'><span class='dot {cls}'></span><span class='status-item-name'>{lbl}</span></div>"
        f"<div class='status-item-msg'>{msg}</div>"
        f"</div>"
        for lbl, cls, msg in items
    )
    return JSONResponse({"html": html})


# ── Chat log recording (called by user_app via internal import or API) ────────
# The user_app records to _chat_log via a shared endpoint below

@app.post("/api/record_chat")
async def api_record_chat(request: Request):
    """Internal endpoint — called by user_app to log chat events for admin analytics."""
    body = await request.json()
    _chat_log.append({
        "employee_id": body.get("employee_id", ""),
        "intent":      body.get("intent", "general"),
        "confidence":  body.get("confidence", 0),
        "query":       body.get("query", ""),
        "model":       body.get("model", ""),
    })
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
