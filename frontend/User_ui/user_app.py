"""
Stafflyx HR AI - Employee Chat Interface (FastAPI)
Professional, clean design. No emojis. Warm + authoritative tone.
Enhanced with: session memory, proactive nudges, suggested follow-ups,
clarifying questions, FAQ shortcuts.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import logging
import uuid
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import COMPANY_NAME
from backend.agents.orchestrator import run_hr_agent
from backend.agents.employee_service import authenticate_employee, get_session_summary
from backend.llm.ollama_client import check_ollama_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"{COMPANY_NAME} HR Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_sessions: dict = {}

SUGGESTED_QUESTIONS = [
    "How many days of annual leave do I have remaining?",
    "What is my current salary and last increment?",
    "When is my next performance review?",
    "What health insurance plan am I enrolled in?",
    "How do I apply for maternity leave?",
    "What is my annual bonus target?",
    "What onboarding training videos are available?",
    "What is the remote work policy?",
    "How does the 401(k) match work?",
    "What is the code of conduct policy?",
]

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NOVACORP_PLACEHOLDER HR Assistant</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#f0eeff;--panel:#ffffff;--blue:#1C1678;--accent:#8576FF;
  --accent2:#6a5edf;--sky:#7BC9FF;--text:#0f0c2e;--muted:#5a5490;
  --border:#d4ceff;--border2:#c5f0e0;--success:#A3FFD6;
  --warn:#d97706;--danger:#dc2626;
  --shadow:0 2px 12px rgba(28,22,120,.1);
  --radius:10px;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif}
body{background:var(--bg);min-height:100vh;padding:16px}
.container{max-width:1340px;margin:0 auto}

/* Header */
.header{
  background:linear-gradient(100deg,#1a3a6b 0%,#1e40af 60%,#1d4ed8 100%);
  border-radius:12px;padding:20px 32px;margin-bottom:18px;
  box-shadow:0 4px 20px rgba(26,58,107,.25);
  display:flex;align-items:center;gap:18px;
}
.header-logo{
  width:44px;height:44px;background:rgba(255,255,255,.15);border-radius:10px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.header-logo svg{width:26px;height:26px;fill:none;stroke:#fff;stroke-width:2}
.header-title{color:#fff;font-size:1.35rem;font-weight:700;letter-spacing:-.01em}
.header-sub{color:rgba(255,255,255,.7);font-size:.78rem;margin-top:2px;text-transform:uppercase;letter-spacing:.06em}
.header-status{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:.78rem;color:rgba(255,255,255,.75)}
.status-dot{width:7px;height:7px;border-radius:50%;background:#34d399}
.status-dot.offline{background:#fbbf24}

/* Card */
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:28px}

/* Login */
#login-view{max-width:440px;margin:40px auto}
.login-heading{font-size:1.25rem;font-weight:700;color:var(--blue);margin-bottom:4px}
.login-sub{color:var(--muted);font-size:.86rem;margin-bottom:24px;line-height:1.5}
.demo-creds{margin-top:20px;border-top:1px solid var(--border);padding-top:16px}
.demo-label{font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:8px}
.demo-table{width:100%;border-collapse:collapse;font-size:.82rem}
.demo-table th{background:#f1f5f9;color:var(--blue);padding:6px 10px;text-align:left;font-weight:600}
.demo-table td{padding:6px 10px;border-top:1px solid var(--border);color:var(--text)}
.demo-table code{font-family:'JetBrains Mono',monospace;font-size:.8em;color:var(--accent);background:#f0eeff;padding:1px 5px;border-radius:4px}

/* Main layout */
#main-view{display:none}
.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.welcome-badge{background:#fff;border:1px solid var(--border2);border-radius:8px;padding:7px 14px;font-size:.86rem;font-weight:600;color:var(--blue);display:flex;align-items:center;gap:8px}
.welcome-badge span{color:var(--muted);font-weight:400}
.layout{display:grid;grid-template-columns:3fr 2fr;gap:16px}
@media(max-width:768px){.layout{grid-template-columns:1fr}}

/* Session memory banner */
.session-banner{
  background:#f0eeff;border:1px solid #bfdbfe;border-radius:8px;
  padding:10px 14px;margin-bottom:12px;font-size:.84rem;color:var(--blue);
  display:flex;align-items:flex-start;gap:10px;line-height:1.5;
}
.session-banner-icon{flex-shrink:0;width:16px;height:16px;margin-top:1px;opacity:.7}

/* Nudge banner */
.nudge-banner{
  background:#fefce8;border:1px solid #fde68a;border-radius:8px;
  padding:10px 14px;margin-bottom:12px;font-size:.84rem;color:#92400e;
  display:flex;align-items:flex-start;gap:10px;line-height:1.5;
}

/* Chat */
#chatbox{height:420px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius);padding:14px;background:#f8fafc;margin-bottom:12px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:82%;padding:10px 14px;border-radius:14px;font-size:.88rem;line-height:1.6}
.msg.user{align-self:flex-end;background:#1e40af;color:#fff;border-radius:14px 14px 4px 14px}
.msg.bot{align-self:flex-start;background:#fff;border:1px solid var(--border);border-radius:14px 14px 14px 4px;box-shadow:0 1px 6px rgba(15,23,42,.06);color:var(--text);white-space:pre-wrap}
.msg.bot.clarify{background:#f0eeff;border-color:#bfdbfe}
.msg-meta{font-size:.72rem;color:var(--muted);margin-top:4px;text-align:right}

/* Clarifying question options */
.clarify-options{display:flex;flex-direction:column;gap:5px;margin-top:8px}
.clarify-opt{background:#fff;border:1.5px solid var(--border2);border-radius:8px;padding:7px 12px;font-size:.83rem;cursor:pointer;color:var(--blue);text-align:left;transition:all .15s;font-family:inherit}
.clarify-opt:hover{background:#f0eeff;border-color:var(--accent)}

/* Follow-up chips */
.followup-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.followup-chip{background:#f1f5f9;border:1.5px solid var(--border);color:var(--blue);border-radius:20px;font-size:.78rem;padding:5px 12px;cursor:pointer;transition:all .15s;white-space:nowrap}
.followup-chip:hover{background:#f0eeff;border-color:var(--accent)}

/* Input row */
.input-row{display:flex;gap:8px;align-items:flex-end}
#msg-input{flex:1;padding:10px 14px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:.88rem;background:#fff;color:var(--text);resize:none;outline:none;font-family:inherit;min-height:44px;max-height:100px}
#msg-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(133,118,255,.1)}

/* Suggested questions */
.sq-label{font-size:.73rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:10px 0 6px}
.suggestions{display:flex;flex-wrap:wrap;gap:5px}
.sug-btn{background:#f8fafc;border:1.5px solid var(--border);color:var(--blue);border-radius:20px;font-size:.77rem;padding:5px 11px;cursor:pointer;transition:all .15s}
.sug-btn:hover{background:#f0eeff;border-color:var(--accent)}

/* Buttons */
.btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent2));border:none;color:#fff;font-weight:600;border-radius:var(--radius);padding:10px 22px;cursor:pointer;font-size:.88rem;transition:all .2s;white-space:nowrap}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(133,118,255,.35)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.btn-secondary{background:#fff;border:1.5px solid var(--border);color:var(--blue);border-radius:var(--radius);padding:8px 16px;cursor:pointer;font-weight:600;font-size:.84rem;transition:background .15s}
.btn-secondary:hover{background:#f1f5f9}
.btn-ghost{background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:.82rem;padding:4px 8px;border-radius:6px}
.btn-ghost:hover{background:var(--bg);color:var(--blue)}

/* Right panel tabs */
.tabs{display:flex;border-bottom:2px solid var(--border);margin-bottom:14px;gap:0}
.tab{padding:8px 15px;cursor:pointer;font-size:.83rem;font-weight:500;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab.active{color:var(--blue);border-bottom-color:var(--accent)}
.tab-content{display:none;font-size:.84rem;color:var(--text);line-height:1.6}
.tab-content.active{display:block}
.tab-content a{color:var(--accent);text-decoration:none}
.tab-content a:hover{text-decoration:underline}
.tab-content code{background:#f1f5f9;color:var(--blue);border-radius:4px;padding:2px 6px;font-family:'JetBrains Mono',monospace;font-size:.8em}

/* Forms */
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:.73rem;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:6px}
.form-group input{width:100%;padding:10px 14px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:.9rem;background:#fff;color:var(--text);outline:none;font-family:inherit}
.form-group input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(133,118,255,.1)}
.error-msg{color:var(--danger);font-size:.83rem;margin-top:8px;min-height:18px}

/* Typing indicator */
.typing{align-self:flex-start;padding:8px 14px;font-size:.83rem;color:var(--muted);background:#fff;border:1px solid var(--border);border-radius:14px;display:flex;align-items:center;gap:6px}
.typing-dot{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:bounce .8s infinite}
.typing-dot:nth-child(2){animation-delay:.15s}
.typing-dot:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}

::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:#f1f5f9}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="header-logo">
      <svg viewBox="0 0 24 24"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
    </div>
    <div>
      <div class="header-title">NOVACORP_PLACEHOLDER HR Assistant</div>
      <div class="header-sub">Employee Self-Service &middot; Powered by Local AI</div>
    </div>
    <div class="header-status" id="ollama-status">
      <span class="status-dot offline"></span> Checking AI engine...
    </div>
  </div>

  <!-- Login View -->
  <div id="login-view" class="card">
    <div class="login-heading">Employee Sign In</div>
    <div class="login-sub">Enter your Employee ID and PIN to access your personal HR information and the Stafflyx knowledge base.</div>
    <div class="form-group"><label>Employee ID</label><input id="emp-id" placeholder="e.g. EMP001" autocomplete="username"/></div>
    <div class="form-group"><label>PIN</label><input id="emp-pin" type="password" placeholder="4-digit PIN" autocomplete="current-password"/></div>
    <button class="btn-primary" onclick="doLogin()" style="width:100%">Sign In</button>
    <div class="error-msg" id="login-err"></div>
    <div class="demo-creds">
      <div class="demo-label">Demo Accounts</div>
      <table class="demo-table">
        <thead><tr><th>Employee ID</th><th>PIN</th><th>Name</th></tr></thead>
        <tbody>
          <tr><td><code>EMP001</code></td><td><code>1234</code></td><td>Alice Johnson</td></tr>
          <tr><td><code>EMP002</code></td><td><code>5678</code></td><td>Brian Martinez</td></tr>
          <tr><td><code>EMP003</code></td><td><code>9012</code></td><td>Carol White</td></tr>
          <tr><td><code>EMP004</code></td><td><code>3456</code></td><td>David Chen</td></tr>
          <tr><td><code>EMP005</code></td><td><code>7890</code></td><td>Priya Sharma</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Main App -->
  <div id="main-view">
    <div class="top-bar">
      <div class="welcome-badge" id="welcome-txt"></div>
      <div style="display:flex;gap:8px">
        <button class="btn-ghost" onclick="clearChat()">Clear Chat</button>
        <button class="btn-secondary" onclick="doLogout()">Sign Out</button>
      </div>
    </div>

    <!-- Session memory banner -->
    <div class="session-banner" id="session-banner" style="display:none">
      <svg class="session-banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      <span id="session-banner-text"></span>
    </div>

    <!-- Nudge banner -->
    <div id="nudge-banner" style="display:none"></div>

    <div class="layout">
      <!-- Left: Chat -->
      <div class="card" style="padding:18px">
        <div id="chatbox"></div>
        <div class="input-row">
          <textarea id="msg-input" rows="2" placeholder="Ask about leave, salary, benefits, policies, performance..."></textarea>
          <button class="btn-primary" id="send-btn" onclick="sendMessage()">Send</button>
        </div>
        <div class="sq-label">Suggested Questions</div>
        <div class="suggestions" id="suggestions"></div>
      </div>

      <!-- Right: Panels -->
      <div class="card" style="padding:18px">
        <div class="tabs">
          <div class="tab active" onclick="switchTab('sources',this)">Sources</div>
          <div class="tab" onclick="switchTab('media',this)">Media</div>
          <div class="tab" onclick="switchTab('ai',this)">AI Info</div>
        </div>
        <div id="tab-sources" class="tab-content active"><p style="color:var(--muted)"><em>Ask a question to see relevant sources.</em></p></div>
        <div id="tab-media" class="tab-content"><p style="color:var(--muted)"><em>Related videos, images, and links will appear here.</em></p></div>
        <div id="tab-ai" class="tab-content"><p style="color:var(--muted)"><em>AI diagnostics will appear after each response.</em></p></div>
      </div>
    </div>
  </div>
</div>

<script>
const SUGGESTIONS = SUGGESTIONS_JSON;
let sessionId = null;
let chatHistory = [];

// Populate suggested questions
const sugDiv = document.getElementById('suggestions');
SUGGESTIONS.forEach(q => {
  const b = document.createElement('button');
  b.className = 'sug-btn'; b.textContent = q;
  b.onclick = () => { document.getElementById('msg-input').value = q; document.getElementById('msg-input').focus(); };
  sugDiv.appendChild(b);
});

// Check Ollama status on load
(async () => {
  try {
    const r = await fetch('/api/ollama_status');
    const d = await r.json();
    const el = document.getElementById('ollama-status');
    if (d.available) {
      el.innerHTML = '<span class="status-dot"></span> AI Engine Online';
    } else {
      el.innerHTML = '<span class="status-dot offline"></span> Demo Mode (Ollama offline)';
    }
  } catch(e){}
})();

function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

async function doLogin() {
  const empId = document.getElementById('emp-id').value.trim().toUpperCase();
  const pin   = document.getElementById('emp-pin').value.trim();
  const errEl = document.getElementById('login-err');
  errEl.textContent = '';
  if (!empId || !pin) { errEl.textContent = 'Please enter your Employee ID and PIN.'; return; }
  const btn = document.querySelector('#login-view .btn-primary');
  btn.disabled = true; btn.textContent = 'Signing in...';
  const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({employee_id: empId, pin})});
  const d = await r.json();
  btn.disabled = false; btn.textContent = 'Sign In';
  if (d.success) {
    sessionId = d.session_id; chatHistory = [];
    document.getElementById('login-view').style.display = 'none';
    document.getElementById('main-view').style.display = 'block';
    // Welcome badge
    const wb = document.getElementById('welcome-txt');
    wb.innerHTML = d.welcome_html;
    // Session memory banner
    if (d.session_summary) {
      document.getElementById('session-banner-text').textContent = d.session_summary;
      document.getElementById('session-banner').style.display = 'flex';
    }
    // Nudges
    if (d.nudges && d.nudges.length > 0) {
      const nb = document.getElementById('nudge-banner');
      nb.style.display = 'block';
      nb.innerHTML = d.nudges.map(n =>
        `<div class="nudge-banner">\u26a0\ufe0f ${n}</div>`
      ).join('');
    }
    addBotMessage(d.greeting, false);
  } else {
    errEl.textContent = d.error;
  }
}

async function doLogout() {
  if (sessionId) {
    await fetch('/api/logout', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id: sessionId})});
  }
  sessionId = null; chatHistory = [];
  document.getElementById('main-view').style.display = 'none';
  document.getElementById('login-view').style.display = 'block';
  document.getElementById('chatbox').innerHTML = '';
  document.getElementById('emp-id').value = '';
  document.getElementById('emp-pin').value = '';
  document.getElementById('session-banner').style.display = 'none';
  document.getElementById('nudge-banner').style.display = 'none';
  resetPanels();
}

function clearChat() {
  document.getElementById('chatbox').innerHTML = '';
  chatHistory = [];
  resetPanels();
}

function resetPanels() {
  document.getElementById('tab-sources').innerHTML = '<p style="color:var(--muted)"><em>Ask a question to see relevant sources.</em></p>';
  document.getElementById('tab-media').innerHTML   = '<p style="color:var(--muted)"><em>Related videos, images, and links will appear here.</em></p>';
  document.getElementById('tab-ai').innerHTML      = '<p style="color:var(--muted)"><em>AI diagnostics will appear after each response.</em></p>';
}

function addUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg user'; div.textContent = text;
  document.getElementById('chatbox').appendChild(div); scrollChat();
}

function addBotMessage(text, isClarify, followups, clarifyOptions) {
  const div = document.createElement('div');
  div.className = 'msg bot' + (isClarify ? ' clarify' : '');
  div.textContent = text;
  document.getElementById('chatbox').appendChild(div);

  // Clarifying options rendered as clickable buttons
  if (clarifyOptions && clarifyOptions.length > 0) {
    const row = document.createElement('div');
    row.className = 'clarify-options';
    clarifyOptions.forEach(opt => {
      const b = document.createElement('button');
      b.className = 'clarify-opt'; b.textContent = opt;
      b.onclick = () => {
        document.getElementById('msg-input').value = opt;
        sendMessage();
      };
      row.appendChild(b);
    });
    document.getElementById('chatbox').appendChild(row);
  }

  // Suggested follow-ups
  if (followups && followups.length > 0) {
    const row = document.createElement('div');
    row.className = 'followup-row';
    followups.forEach(f => {
      const b = document.createElement('button');
      b.className = 'followup-chip'; b.textContent = f;
      b.onclick = () => {
        document.getElementById('msg-input').value = f;
        sendMessage();
      };
      row.appendChild(b);
    });
    document.getElementById('chatbox').appendChild(row);
  }
  scrollChat();
}

function scrollChat() {
  const cb = document.getElementById('chatbox'); cb.scrollTop = cb.scrollHeight;
}

async function sendMessage() {
  const input   = document.getElementById('msg-input');
  const sendBtn = document.getElementById('send-btn');
  const msg     = input.value.trim();
  if (!msg || !sessionId) return;
  input.value = ''; input.disabled = true;
  sendBtn.disabled = true; sendBtn.textContent = '...';
  addUserMessage(msg);

  const typing = document.createElement('div');
  typing.className = 'typing';
  typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
  document.getElementById('chatbox').appendChild(typing); scrollChat();

  try {
    const r = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId, message: msg, history: chatHistory})
    });
    const d = await r.json();
    typing.remove();
    addBotMessage(d.answer, d.is_clarify, d.suggested_followups, d.clarify_options);
    chatHistory.push({role:'user', content: msg});
    chatHistory.push({role:'assistant', content: d.answer});
    document.getElementById('tab-sources').innerHTML = d.sources_html;
    document.getElementById('tab-media').innerHTML   = d.media_html;
    document.getElementById('tab-ai').innerHTML      = d.ai_html;
  } catch(err) {
    typing.remove();
    addBotMessage('A connection error occurred. Please try again or contact the HR team at hr@stafflyx.com.');
    console.error(err);
  } finally {
    input.disabled = false;
    sendBtn.disabled = false; sendBtn.textContent = 'Send';
    input.focus();
  }
}

document.getElementById('msg-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
</script>
</body>
</html>
"""


def _get_html():
    return HTML_PAGE.replace("NOVACORP_PLACEHOLDER", COMPANY_NAME).replace("SUGGESTIONS_JSON", json.dumps(SUGGESTED_QUESTIONS))


def _build_sources_html(result: dict) -> str:
    sources = result.get("sources", [])
    if not sources:
        return "<p><em>No specific sources retrieved for this query.</em></p>"
    lines = ["<strong style='color:var(--blue)'>Retrieved Sources</strong><br/><br/>"]
    for cite in sources:
        title       = cite.get("title", cite.get("file_name", "Document"))
        source_type = cite.get("source_type", "doc").upper()
        score       = cite.get("relevance_score", 0)
        score_pct   = int(score * 100)
        url         = cite.get("url", "")
        excerpt     = cite.get("excerpt", "")
        bar_filled  = "&block;" * (score_pct // 10)
        bar_empty   = "&#9617;" * (10 - score_pct // 10)
        t = f'<a href="{url}" target="_blank">{title}</a>' if url else title
        lines.append(f"<strong>{t}</strong><br/>")
        lines.append(f"<span style='color:var(--muted);font-size:.78rem'>{source_type} &middot; Relevance: <code>{bar_filled}{bar_empty}</code> {score_pct}%</span><br/>")
        if excerpt:
            lines.append(f"<blockquote style='border-left:3px solid var(--border2);padding-left:10px;color:var(--muted);margin:4px 0;font-size:.82rem'>{excerpt[:120]}...</blockquote>")
        lines.append("<br/>")
    return "".join(lines)


def _build_media_html(result: dict) -> str:
    grouped = result.get("grouped_sources", {})
    videos  = grouped.get("video", [])
    links   = grouped.get("link", [])
    images  = grouped.get("image", [])
    if not videos and not links and not images:
        return "<p><em>No multimedia resources found for this query.</em></p>"
    lines = []
    if videos:
        lines.append("<strong style='color:var(--blue)'>Training Videos</strong><ul style='padding-left:16px;margin:6px 0'>")
        for v in videos[:3]:
            url   = v.get("url", ""); title = v.get("title", "Training Video")
            lines.append(f'<li><a href="{url}" target="_blank">{title}</a></li>' if url else f"<li>{title}</li>")
        lines.append("</ul>")
    if links:
        lines.append("<strong style='color:var(--blue)'>Helpful Links</strong><ul style='padding-left:16px;margin:6px 0'>")
        for lk in links[:4]:
            url   = lk.get("url", ""); title = lk.get("title", "HR Resource")
            lines.append(f'<li><a href="{url}" target="_blank">{title}</a></li>' if url else f"<li>{title}</li>")
        lines.append("</ul>")
    if images:
        lines.append("<strong style='color:var(--blue)'>Visual Resources</strong><ul style='padding-left:16px;margin:6px 0'>")
        for img in images[:2]:
            lines.append(f"<li>{img.get('title','HR Image')}</li>")
        lines.append("</ul>")
    return "".join(lines)


def _build_ai_html(result: dict) -> str:
    intent      = result.get("intent", "general").replace("_", " ").title()
    confidence  = int(result.get("intent_confidence", 0) * 100)
    top_score   = int(result.get("top_score", 0) * 100)
    retrieved   = result.get("retrieved_count", 0)
    model       = result.get("model", "unknown")
    used_ollama = result.get("used_ollama", False)
    if used_ollama:
        model_label = "Ollama LLM (Online)"
        model_color = "var(--success)"
    elif model in ("faq-cache", "faq-personalised"):
        model_label = "FAQ Cache (Instant)"
        model_color = "var(--sky)"
    elif model == "clarification":
        model_label = "Clarification Mode"
        model_color = "var(--warn)"
    else:
        model_label = "Demo Mode (Ollama offline)"
        model_color = "var(--warn)"
    return (
        f"<strong style='color:var(--blue)'>AI Diagnostics</strong><br/><br/>"
        f"<b>Intent Detected:</b> <code>{intent}</code><br/>"
        f"<b>Intent Confidence:</b> {confidence}%<br/>"
        f"<b>KB Relevance Score:</b> {top_score}%<br/>"
        f"<b>Chunks Retrieved:</b> {retrieved}<br/>"
        f"<b>Response Mode:</b> <span style='color:{model_color};font-weight:600'>{model_label}</span><br/>"
        f"<b>Model ID:</b> <code>{model}</code>"
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return _get_html()


@app.get("/api/ollama_status")
async def api_ollama_status():
    available = await asyncio.to_thread(check_ollama_available)
    return JSONResponse({"available": available})


@app.post("/api/login")
async def api_login(request: Request):
    body   = await request.json()
    emp_id = body.get("employee_id", "").strip().upper()
    pin    = body.get("pin", "").strip()
    emp    = await asyncio.to_thread(authenticate_employee, emp_id, pin)
    if emp:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = {"employee_id": emp["employee_id"], "employee_name": emp["name"]}
        # Load session memory
        summary = await asyncio.to_thread(get_session_summary, emp["employee_id"])
        # Proactive nudges
        from backend.agents.employee_service import get_proactive_nudges
        nudges = get_proactive_nudges(emp)
        # Personalised greeting
        first_name = emp["name"].split()[0]
        greeting = (
            f"Welcome back, {first_name}. I'm ready to assist you with your HR queries.\n\n"
            f"You can ask me about your leave balance, salary, benefits, performance review, "
            f"company policies, and more. How can I help you today?"
        )
        welcome_html = f"{emp['name']} &nbsp;<span>{emp.get('role','Employee')}</span>"
        return JSONResponse({
            "success": True, "session_id": session_id,
            "welcome_html": welcome_html,
            "greeting": greeting,
            "session_summary": summary,
            "nudges": nudges
        })
    return JSONResponse({"success": False, "error": "Invalid Employee ID or PIN. Please try again."})


@app.post("/api/logout")
async def api_logout(request: Request):
    body = await request.json()
    _sessions.pop(body.get("session_id", ""), None)
    return JSONResponse({"success": True})


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list = []


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await asyncio.to_thread(run_hr_agent, req.message, session["employee_id"], req.history)
    clarify         = result.get("clarifying_question")
    is_clarify      = clarify is not None
    clarify_options = clarify["options"] if clarify else []

    # Record to admin analytics (fire-and-forget, non-blocking)
    try:
        import httpx as _httpx
        _httpx.post(
            "http://127.0.0.1:7860/api/record_chat",
            json={
                "employee_id": session["employee_id"],
                "intent":      result.get("intent", "general"),
                "confidence":  result.get("intent_confidence", 0),
                "query":       req.message[:200],
                "model":       result.get("model", ""),
            },
            timeout=1.0
        )
    except Exception:
        pass  # Admin may not be running — never fail a chat request because of this

    return JSONResponse({
        "answer":              result["answer"],
        "sources_html":        _build_sources_html(result),
        "media_html":          _build_media_html(result),
        "ai_html":             _build_ai_html(result),
        "suggested_followups": result.get("suggested_followups", []),
        "is_clarify":          is_clarify,
        "clarify_options":     clarify_options,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7861)
