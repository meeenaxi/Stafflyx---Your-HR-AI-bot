"""
NovaCorp HR AI - Agentic Orchestrator (v2)
Enhanced with:
  - FAQ cache shortcuts
  - Clarifying questions when confidence < 0.6
  - Session memory (load + save)
  - Proactive nudges
  - Frustration detection + escalation
  - Personalized greeting with last-session context
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
import re
from typing import Dict, Any, Optional, List

from backend.agents.query_agent import classify_intent
from backend.agents.employee_service import (
    get_employee_by_id, get_session_summary, save_session_summary, get_proactive_nudges
)
from backend.agents.source_agent import build_source_citations
from backend.retrieval.retriever import retrieve_and_rerank
from backend.llm.ollama_client import generate_answer

logger = logging.getLogger(__name__)

# ─── Frustration keywords → escalation ───────────────────────────────────────

FRUSTRATION_PATTERNS = [
    r"\b(useless|stupid|terrible|awful|broken|not working|frustrated|angry|hate this)\b",
    r"\b(this is wrong|incorrect|bad answer|wrong answer|terrible response)\b",
    r"\b(speak to (a |an )?(human|person|someone|hr|representative))\b",
    r"\b(escalate|escalation|complaint|formal complaint)\b",
    r"\b(not helpful|unhelpful|doesn't help)\b",
]


def _detect_frustration(query: str) -> bool:
    q = query.lower()
    return any(re.search(p, q) for p in FRUSTRATION_PATTERNS)


def _escalation_response(employee_name: str) -> str:
    name = employee_name or "there"
    return (
        f"I'm sorry to hear you're having difficulty, {name}. "
        f"I want to make sure you get the right help.\n\n"
        f"You can reach the HR team directly through the following channels:\n\n"
        f"- Email: hr@novacorp.com\n"
        f"- Phone: ext. 4000\n"
        f"- HR Portal: hr.novacorp.com\n"
        f"- Office Hours: Monday to Friday, 9:00 AM to 5:30 PM\n\n"
        f"A member of the team will be happy to assist you personally."
    )


# ─── Dynamic FAQ answers using employee data ─────────────────────────────────

def _build_faq_answer(answer_key: str, employee_data: Optional[Dict]) -> Optional[str]:
    """Build a personalised answer from FAQ cache + employee data."""
    if not employee_data:
        return None

    name = employee_data.get("name", "there")

    if answer_key == "leave_balance":
        leave = employee_data.get("leave", {})
        ann_rem  = leave.get("annual_remaining", "N/A")
        ann_used = leave.get("annual_used", "N/A")
        ann_tot  = leave.get("annual_total", "N/A")
        sick_rem = leave.get("sick_remaining", "N/A")
        cas_rem  = leave.get("casual_remaining", "N/A")
        return (
            f"Here is your current leave summary, {name}:\n\n"
            f"- Annual Leave: {ann_rem} days remaining ({ann_used} used out of {ann_tot})\n"
            f"- Sick Leave: {sick_rem} days remaining\n"
            f"- Casual Leave: {cas_rem} days remaining\n\n"
            f"To apply for leave, visit hr.novacorp.com and navigate to My Leave > Apply for Leave. "
            f"Annual leave requests require at least 5 working days advance notice."
        )

    if answer_key == "next_review":
        perf = employee_data.get("performance", {})
        next_rev = perf.get("next_review_date", "N/A")
        score = perf.get("last_review_score", "N/A")
        goals_done = perf.get("goals_completed", 0)
        goals_total = perf.get("goals_total", 0)
        return (
            f"Here is your performance overview, {name}:\n\n"
            f"- Next Review Date: {next_rev}\n"
            f"- Last Review Score: {score}/5\n"
            f"- Goals Completed: {goals_done} out of {goals_total}\n\n"
            f"You can view your full performance record and update your goals on the HR portal under Performance > My Reviews."
        )

    if answer_key == "bonus_target":
        inc = employee_data.get("incentives", {})
        bonus_pct = inc.get("annual_bonus_target_pct", "N/A")
        sal = employee_data.get("salary", {})
        base = sal.get("base_salary", 0)
        try:
            target_amt = float(str(bonus_pct).replace('%','')) / 100 * float(base)
            amt_str = f" (approximately ${target_amt:,.0f} at current base salary)"
        except Exception:
            amt_str = ""
        return (
            f"Your annual bonus target is {bonus_pct}% of your base salary{amt_str}, {name}.\n\n"
            f"Bonus payouts are tied to your individual performance rating and the company's overall performance. "
            f"Bonuses are typically paid in Q1 of the following year."
        )

    if answer_key == "health_insurance":
        ben = employee_data.get("benefits", {})
        plan = ben.get("health_insurance", "N/A")
        return (
            f"You are enrolled in the **{plan}** health insurance plan, {name}.\n\n"
            f"For a full breakdown of coverage, co-pays, and in-network providers, "
            f"please visit the Benefits Portal at benefits.novacorp.com or contact benefits@novacorp.com."
        )

    if answer_key == "stock_options":
        inc = employee_data.get("incentives", {})
        opts = inc.get("stock_options", inc.get("stock_options", "N/A"))
        return (
            f"Your current stock option status, {name}:\n\n"
            f"- Stock Options: {opts}\n\n"
            f"For vesting schedules and exercise instructions, please contact equity@novacorp.com "
            f"or refer to your original offer letter and the Equity section of the HR portal."
        )

    return None


# ─── Main orchestrator ────────────────────────────────────────────────────────

def run_hr_agent(
    query: str,
    employee_id: Optional[str] = None,
    chat_history: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Synchronous main entry point for the HR AI agentic workflow.
    Call via: await asyncio.to_thread(run_hr_agent, query, employee_id, chat_history)
    """
    logger.info(f"[Agent] Query: {query[:80]} | Employee: {employee_id}")

    # ── Frustration / escalation detection ───────────────────────────────────
    if _detect_frustration(query):
        employee_data = get_employee_by_id(employee_id) if employee_id else None
        emp_name = (employee_data or {}).get("name", "")
        return {
            "answer": _escalation_response(emp_name),
            "sources": [], "grouped_sources": {},
            "intent": "escalation", "intent_confidence": 1.0,
            "model": "rule-based", "used_ollama": False,
            "retrieved_count": 0, "top_score": 0,
            "employee_name": emp_name,
            "clarifying_question": None,
            "suggested_followups": [],
            "nudges": []
        }

    # ── Agent 1: Query Understanding ──────────────────────────────────────────
    intent_result = classify_intent(query)
    intent          = intent_result["intent"]
    needs_personal  = intent_result["needs_personal_data"]
    kb_hint         = intent_result["kb_category_hint"]
    confidence      = intent_result["confidence"]
    clarifying      = intent_result.get("clarifying_question")
    faq_match       = intent_result.get("faq_match")

    logger.info(f"[Agent 1] Intent: {intent} | Confidence: {confidence} | FAQ: {faq_match is not None}")

    # ── Load personal employee data ───────────────────────────────────────────
    employee_data = None
    employee_name = None
    if employee_id:
        employee_data = get_employee_by_id(employee_id)
        if employee_data:
            employee_name = employee_data.get("name")

    # ── Proactive nudges ──────────────────────────────────────────────────────
    nudges = []
    if employee_data:
        nudges = get_proactive_nudges(employee_data)

    # ── FAQ Shortcut: personalised answer without RAG ─────────────────────────
    if faq_match and faq_match.get("static_answer"):
        answer = faq_match["static_answer"]
        save_session_summary(employee_id or "", intent, f"Asked about: {intent}")
        return {
            "answer": answer,
            "sources": [], "grouped_sources": {},
            "intent": intent, "intent_confidence": confidence,
            "model": "faq-cache", "used_ollama": False,
            "retrieved_count": 0, "top_score": 0,
            "employee_name": employee_name,
            "clarifying_question": None,
            "suggested_followups": _get_suggested_followups(intent),
            "nudges": nudges
        }

    if faq_match and employee_data:
        personalised = _build_faq_answer(faq_match["answer_key"], employee_data)
        if personalised:
            save_session_summary(employee_id or "", intent, f"Asked about: {faq_match['answer_key']}")
            return {
                "answer": personalised,
                "sources": [], "grouped_sources": {},
                "intent": intent, "intent_confidence": confidence,
                "model": "faq-personalised", "used_ollama": False,
                "retrieved_count": 0, "top_score": 0,
                "employee_name": employee_name,
                "clarifying_question": None,
                "suggested_followups": _get_suggested_followups(intent),
                "nudges": nudges
            }

    # ── Clarifying question when confidence is low ────────────────────────────
    if confidence < 0.6 and clarifying:
        return {
            "answer": f"{clarifying['question']}\n\n" + "\n".join(
                f"- {opt}" for opt in clarifying["options"]
            ),
            "sources": [], "grouped_sources": {},
            "intent": intent, "intent_confidence": confidence,
            "model": "clarification", "used_ollama": False,
            "retrieved_count": 0, "top_score": 0,
            "employee_name": employee_name,
            "clarifying_question": clarifying,
            "suggested_followups": [],
            "nudges": nudges
        }

    # ── Agent 2: Retrieval ────────────────────────────────────────────────────
    retrieval_result = retrieve_and_rerank(query=query, category_filter=kb_hint)
    chunks  = retrieval_result["chunks"]
    grouped = retrieval_result["grouped"]
    logger.info(f"[Agent 2] Retrieved {retrieval_result['retrieved_count']} chunks")

    # ── Agent 3: Context Builder ──────────────────────────────────────────────
    text_chunks  = grouped.get("text", [])
    video_chunks = grouped.get("video", [])
    link_chunks  = grouped.get("link", [])
    image_chunks = grouped.get("image", [])

    llm_context = text_chunks.copy()
    llm_context += video_chunks[:2]
    llm_context += link_chunks[:2]

    # ── Agent 4: Answer Generation ────────────────────────────────────────────
    llm_result = generate_answer(
        query=query,
        context_chunks=llm_context,
        employee_data=employee_data if needs_personal else None,
        chat_history=chat_history
    )
    logger.info(f"[Agent 4] Answer via {llm_result['model']}")

    # ── Agent 5: Source Attribution ───────────────────────────────────────────
    citations = build_source_citations(chunks)

    # ── Save session summary ──────────────────────────────────────────────────
    if employee_id:
        summary = f"Asked about {intent}. Query: {query[:80]}"
        save_session_summary(employee_id, intent, summary)

    return {
        "answer": llm_result["answer"],
        "sources": citations,
        "grouped_sources": {
            "text":  [{"title": c.get("metadata", {}).get("file_name", "Doc"), "excerpt": c["text"][:200]} for c in text_chunks],
            "video": [{"title": c.get("metadata", {}).get("title", "Video"), "url": c.get("metadata", {}).get("url", ""), "excerpt": c["text"][:200]} for c in video_chunks],
            "image": [{"title": c.get("metadata", {}).get("title", "Image"), "file": c.get("metadata", {}).get("file_name", ""), "excerpt": c["text"][:200]} for c in image_chunks],
            "link":  [{"title": c.get("metadata", {}).get("title", "Link"), "url": c.get("metadata", {}).get("url", ""), "excerpt": c["text"][:200]} for c in link_chunks],
        },
        "intent": intent,
        "intent_confidence": confidence,
        "model": llm_result["model"],
        "used_ollama": llm_result["used_ollama"],
        "retrieved_count": retrieval_result["retrieved_count"],
        "top_score": retrieval_result["top_score"],
        "employee_name": employee_name,
        "clarifying_question": None,
        "suggested_followups": _get_suggested_followups(intent),
        "nudges": nudges
    }


def _get_suggested_followups(intent: str) -> List[str]:
    """Return contextual follow-up suggestions based on the current intent."""
    MAP = {
        "leave":       ["How do I apply for leave?", "What is the maternity leave policy?", "What counts as sick leave?"],
        "salary":      ["When is my next payslip available?", "How are increments decided?", "What is my bonus target?"],
        "incentives":  ["How are stock options vested?", "When is the bonus paid?", "What is the referral bonus?"],
        "benefits":    ["What does my health insurance cover?", "How does the 401(k) match work?", "What is my learning budget?"],
        "training":    ["What onboarding videos are available?", "How do I access the LMS?", "What courses are recommended?"],
        "performance": ["When is my next performance review?", "How do I set my goals?", "What is the PIP process?"],
        "policy":      ["What is the remote work policy?", "What is the code of conduct?", "What is the harassment policy?"],
        "general":     ["What is my leave balance?", "When is my next review?", "What benefits am I enrolled in?"],
    }
    return MAP.get(intent, MAP["general"])
