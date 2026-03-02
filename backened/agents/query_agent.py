"""
NovaCorp HR AI - Query Understanding Agent
Classifies employee queries into intent categories and generates clarifying questions
when confidence is low.
"""

import re
from typing import Dict, Any, List

# ─── Intent patterns ──────────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "leave": [
        r"\bleave\b", r"\bvacation\b", r"\btime.?off\b", r"\bsick\b", r"\bcasual\b",
        r"\bholiday\b", r"\bmaternity\b", r"\bpaternity\b", r"\bbereavement\b",
        r"\babsence\b", r"\bday.?off\b", r"\bbalance\b"
    ],
    "salary": [
        r"\bsalary\b", r"\bpay\b", r"\bpayslip\b", r"\bcompensation\b", r"\bincrement\b",
        r"\braise\b", r"\bincrease\b", r"\bearning\b", r"\bwage\b", r"\bctc\b",
        r"\bmonthly.?pay\b", r"\bbase.?salary\b"
    ],
    "incentives": [
        r"\bbonus\b", r"\bincentive\b", r"\bstock\b", r"\bequity\b", r"\boption\b",
        r"\breferral\b", r"\breward\b", r"\bspot.?award\b", r"\bvariable\b"
    ],
    "benefits": [
        r"\bbenefit\b", r"\binsurance\b", r"\bhealth\b", r"\bdental\b", r"\bvision\b",
        r"\b401k\b", r"\bretirement\b", r"\bwellness\b", r"\bgym\b", r"\beap\b",
        r"\bchildcare\b", r"\bstipend\b", r"\blearning.?budget\b"
    ],
    "training": [
        r"\btraining\b", r"\bcourse\b", r"\blearn\b", r"\bcertif\b", r"\bvideo\b",
        r"\bonboard\b", r"\bworkshop\b", r"\bmodule\b", r"\blms\b", r"\bskill\b"
    ],
    "performance": [
        r"\bperformance\b", r"\breview\b", r"\brating\b", r"\bgoal\b", r"\bokr\b",
        r"\bkpi\b", r"\bfeedback\b", r"\bappraisal\b", r"\bassessment\b", r"\bpip\b"
    ],
    "policy": [
        r"\bpolic\b", r"\bprocedure\b", r"\brule\b", r"\bguideline\b", r"\bcode\b",
        r"\bconduct\b", r"\bcomplian\b", r"\bharassment\b", r"\bdiversit\b",
        r"\bremote\b", r"\bwfh\b", r"\bwork.?from.?home\b"
    ],
    "general": []
}

CATEGORY_HINT = {
    "leave":       "policies",
    "salary":      "policies",
    "incentives":  "policies",
    "benefits":    "benefits",
    "training":    "training",
    "performance": "policies",
    "policy":      "policies",
    "general":     None
}

PERSONAL_DATA_INTENTS = {"leave", "salary", "incentives", "performance"}

# ─── FAQ shortcuts (bypass RAG for speed) ────────────────────────────────────
# Maps regex pattern → (answer template, intent)
FAQ_CACHE: List[Dict] = [
    {
        "patterns": [r"\bhow many.*(leave|vacation|days off)\b", r"\bleave balance\b", r"\bdays.*remaining\b"],
        "intent": "leave",
        "answer_key": "leave_balance",
    },
    {
        "patterns": [r"\bwhen.*payslip\b", r"\bpayslip.*date\b", r"\bwhen.*paid\b", r"\bpay.*date\b"],
        "intent": "salary",
        "answer_key": "payslip_date",
        "static_answer": "Payslips are made available on the HR portal by the 25th of each month. You can download them from hr.novacorp.com under 'My Payslips'. For any discrepancies, please contact payroll@novacorp.com."
    },
    {
        "patterns": [r"\bhow.*apply.*leave\b", r"\bleave.*application\b", r"\bapply.*time off\b"],
        "intent": "leave",
        "answer_key": "apply_leave",
        "static_answer": "To apply for leave, log in to the HR portal at hr.novacorp.com and navigate to My Leave > Apply for Leave. Annual leave requests require a minimum of 5 working days advance notice. Sick leave should be reported to your manager on the same day."
    },
    {
        "patterns": [r"\b(what|how).*(401k|retirement|match)\b"],
        "intent": "benefits",
        "answer_key": "401k",
        "static_answer": "NovaCorp matches 401(k) contributions up to 5% of your base salary for standard-grade employees, and up to 6% for executive-level staff. Contributions are fully vested after 3 years of service. You can update your contribution rate via the Benefits Portal at benefits.novacorp.com."
    },
    {
        "patterns": [r"\b(what|when).*(performance review|appraisal)\b", r"\bnext review\b"],
        "intent": "performance",
        "answer_key": "next_review",
    },
    {
        "patterns": [r"\bbonus.*target\b", r"\bwhat.*bonus\b", r"\bhow much.*bonus\b"],
        "intent": "incentives",
        "answer_key": "bonus_target",
    },
    {
        "patterns": [r"\bremote.*(work|policy|wfh)\b", r"\bwork from home\b", r"\bwfh policy\b"],
        "intent": "policy",
        "answer_key": "remote_work",
        "static_answer": "NovaCorp operates a hybrid work model. Employees may work remotely up to 3 days per week, subject to manager approval and role requirements. Fully remote arrangements require VP-level sign-off. Please refer to the Remote Work Policy on the HR portal for full details."
    },
    {
        "patterns": [r"\bhealth insurance\b", r"\bmedical (plan|insurance|coverage)\b"],
        "intent": "benefits",
        "answer_key": "health_insurance",
    },
    {
        "patterns": [r"\bstock (option|grant|equity)\b", r"\bvested\b", r"\bunvested\b"],
        "intent": "incentives",
        "answer_key": "stock_options",
    },
    {
        "patterns": [r"\bcontact hr\b", r"\bhr email\b", r"\bhr phone\b", r"\breach hr\b"],
        "intent": "general",
        "answer_key": "hr_contact",
        "static_answer": "You can reach the HR team through the following channels:\n\n- Email: hr@novacorp.com\n- Phone: ext. 4000\n- Portal: hr.novacorp.com\n- Office hours: Monday to Friday, 9:00 AM to 5:30 PM"
    },
]


# ─── Clarifying questions per ambiguous intent ────────────────────────────────

CLARIFYING_QUESTIONS = {
    "leave": {
        "question": "To assist you more precisely, could you let me know what you need help with?",
        "options": [
            "Check my current leave balance",
            "Understand NovaCorp leave policy",
            "Apply for leave or find out the process",
            "Ask about a specific leave type (sick, maternity, etc.)"
        ]
    },
    "salary": {
        "question": "I want to make sure I give you the right information. Are you asking about:",
        "options": [
            "My current salary and last increment",
            "When payslips are issued",
            "The salary increment / appraisal cycle",
            "Compensation policy in general"
        ]
    },
    "general": {
        "question": "I want to make sure I help you with the right topic. Which area can I assist you with?",
        "options": [
            "Leave and time off",
            "Salary and payslips",
            "Benefits and insurance",
            "Performance and goals"
        ]
    }
}


def check_faq_cache(query: str) -> Dict[str, Any]:
    """
    Check if query matches a cached FAQ for fast response.
    Returns {"matched": bool, "answer_key": str, "static_answer": str|None, "intent": str}
    """
    q = query.lower()
    for faq in FAQ_CACHE:
        for pattern in faq["patterns"]:
            if re.search(pattern, q):
                return {
                    "matched": True,
                    "answer_key": faq["answer_key"],
                    "static_answer": faq.get("static_answer"),
                    "intent": faq["intent"]
                }
    return {"matched": False, "answer_key": None, "static_answer": None, "intent": None}


def classify_intent(query: str) -> Dict[str, Any]:
    """
    Classify the intent of an HR query.

    Returns:
        {
            "intent": str,
            "confidence": float,
            "needs_personal_data": bool,
            "kb_category_hint": str | None,
            "clarifying_question": dict | None,   # if confidence < 0.6
            "faq_match": dict | None               # if matches FAQ cache
        }
    """
    q = query.lower()

    # FAQ shortcut check
    faq = check_faq_cache(q)

    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        if not patterns:
            scores[intent] = 0
            continue
        hits = sum(1 for p in patterns if re.search(p, q))
        scores[intent] = hits

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    if best_score == 0:
        best_intent = "general"
        confidence = 0.3
    elif best_score == 1:
        confidence = 0.6
    elif best_score == 2:
        confidence = 0.8
    else:
        confidence = 0.95

    personal_keywords = re.search(r"\b(my|i |i'm|i've|me |mine)\b", q)
    needs_personal = best_intent in PERSONAL_DATA_INTENTS or bool(personal_keywords)

    # If confidence is low, generate a clarifying question
    clarifying = None
    if confidence < 0.6 and best_intent in CLARIFYING_QUESTIONS:
        clarifying = CLARIFYING_QUESTIONS[best_intent]
    elif confidence < 0.6:
        clarifying = CLARIFYING_QUESTIONS["general"]

    return {
        "intent": best_intent,
        "confidence": confidence,
        "needs_personal_data": needs_personal,
        "kb_category_hint": CATEGORY_HINT.get(best_intent),
        "clarifying_question": clarifying,
        "faq_match": faq if faq["matched"] else None
    }
