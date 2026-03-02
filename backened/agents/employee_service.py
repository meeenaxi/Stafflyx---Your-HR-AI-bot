"""
NovaCorp HR AI - Employee Data Service (MySQL Edition)
Reads all employee data from MySQL. Falls back to JSON if MySQL is unavailable.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, date

logger = logging.getLogger(__name__)

# ─── MySQL helper ─────────────────────────────────────────────────────────────

def _get_mysql_conn():
    """Return a MySQL connection or raise."""
    try:
        import mysql.connector
        from config.settings import (
            MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
            MYSQL_DATABASE, MYSQL_AUTH_PLUGIN
        )
        return mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            connection_timeout=5,
            auth_plugin=MYSQL_AUTH_PLUGIN,
            use_pure=True,
        )
    except Exception as e:
        raise ConnectionError(f"MySQL unavailable: {e}")


def _row_to_dict(cursor) -> List[Dict]:
    """Convert cursor fetchall to list of dicts using column names."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _serialize(obj):
    """Make dates JSON-serialisable."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def _fetch_employee_mysql(employee_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full employee record from MySQL (all related tables)."""
    try:
        conn = _get_mysql_conn()
        cur = conn.cursor()

        # Core info
        cur.execute("SELECT * FROM employees WHERE employee_id = %s", (employee_id,))
        rows = _row_to_dict(cur)
        if not rows:
            cur.close(); conn.close()
            return None
        emp = {k: _serialize(v) for k, v in rows[0].items()}

        def _fetch_related(table):
            cur.execute(f"SELECT * FROM {table} WHERE employee_id = %s", (employee_id,))
            r = _row_to_dict(cur)
            return {k: _serialize(v) for k, v in r[0].items()} if r else {}

        # Try both table name variants (the two SQL files use different names)
        for leave_table in ("leave_balances", "employee_leave"):
            try:
                cur.execute(f"SELECT * FROM {leave_table} WHERE employee_id = %s", (employee_id,))
                r = _row_to_dict(cur)
                emp["leave"] = {k: _serialize(v) for k, v in r[0].items()} if r else {}
                break
            except Exception:
                emp["leave"] = {}

        for sal_table in ("salary", "employee_salary"):
            try:
                cur.execute(f"SELECT * FROM {sal_table} WHERE employee_id = %s", (employee_id,))
                r = _row_to_dict(cur)
                emp["salary"] = {k: _serialize(v) for k, v in r[0].items()} if r else {}
                break
            except Exception:
                emp["salary"] = {}

        for ben_table in ("benefits", "employee_benefits"):
            try:
                cur.execute(f"SELECT * FROM {ben_table} WHERE employee_id = %s", (employee_id,))
                r = _row_to_dict(cur)
                emp["benefits"] = {k: _serialize(v) for k, v in r[0].items()} if r else {}
                break
            except Exception:
                emp["benefits"] = {}

        for inc_table in ("incentives", "employee_incentives"):
            try:
                cur.execute(f"SELECT * FROM {inc_table} WHERE employee_id = %s", (employee_id,))
                r = _row_to_dict(cur)
                emp["incentives"] = {k: _serialize(v) for k, v in r[0].items()} if r else {}
                break
            except Exception:
                emp["incentives"] = {}

        for perf_table in ("performance", "employee_performance"):
            try:
                cur.execute(f"SELECT * FROM {perf_table} WHERE employee_id = %s", (employee_id,))
                r = _row_to_dict(cur)
                emp["performance"] = {k: _serialize(v) for k, v in r[0].items()} if r else {}
                break
            except Exception:
                emp["performance"] = {}

        cur.close(); conn.close()
        return emp
    except Exception as e:
        logger.warning(f"MySQL fetch failed for {employee_id}: {e}")
        return None


def _fetch_all_employees_mysql() -> List[Dict]:
    """Fetch all employees from MySQL."""
    try:
        conn = _get_mysql_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM employees ORDER BY employee_id")
        rows = _row_to_dict(cur)
        cur.close(); conn.close()
        return [{k: _serialize(v) for k, v in r.items()} for r in rows]
    except Exception as e:
        logger.warning(f"MySQL fetchall failed: {e}")
        return []


# ─── JSON fallback ────────────────────────────────────────────────────────────

def _load_json_employees() -> list:
    try:
        from config.settings import EMPLOYEE_DATA_DIR
        f = EMPLOYEE_DATA_DIR / "employees.json"
        data = json.loads(f.read_text())
        return data.get("employees", [])
    except Exception as e:
        logger.error(f"JSON fallback failed: {e}")
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

def authenticate_employee(employee_id: str, pin: str) -> Optional[Dict[str, Any]]:
    """Authenticate employee by ID + PIN. MySQL first, JSON fallback."""
    emp = _fetch_employee_mysql(employee_id.upper())
    if emp:
        if str(emp.get("pin", "")) == str(pin):
            return emp
        return None

    # JSON fallback
    for e in _load_json_employees():
        if e["employee_id"].upper() == employee_id.upper() and e["pin"] == pin:
            return e
    return None


def get_employee_by_id(employee_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full employee record by ID. MySQL first, JSON fallback."""
    emp = _fetch_employee_mysql(employee_id.upper())
    if emp:
        return emp
    for e in _load_json_employees():
        if e["employee_id"].upper() == employee_id.upper():
            return e
    return None


def get_employee_list() -> list:
    """Return summary list of all employees for admin view."""
    rows = _fetch_all_employees_mysql()
    if rows:
        return [
            {
                "employee_id": r.get("employee_id"),
                "name": r.get("name"),
                "department": r.get("department"),
                "role": r.get("role"),
                "grade": r.get("grade"),
                "join_date": r.get("join_date"),
                "email": r.get("email"),
            }
            for r in rows
        ]
    return [
        {
            "employee_id": e["employee_id"],
            "name": e["name"],
            "department": e["department"],
            "role": e["role"],
        }
        for e in _load_json_employees()
    ]


# ─── Session Memory (MySQL) ───────────────────────────────────────────────────

def get_session_summary(employee_id: str) -> Optional[str]:
    """Load last session summary from MySQL."""
    try:
        conn = _get_mysql_conn()
        cur = conn.cursor()
        # Try both table name variants
        for tbl in ("sessions", "session_memory"):
            try:
                cur.execute(
                    f"SELECT last_topic, summary FROM {tbl} "
                    f"WHERE employee_id = %s ORDER BY updated_at DESC LIMIT 1",
                    (employee_id,)
                )
                row = cur.fetchone()
                if row:
                    cur.close(); conn.close()
                    last_topic, summary = row
                    if summary:
                        return summary
                    if last_topic:
                        return f"Last time we discussed: {last_topic}."
                    return None
            except Exception:
                continue
        cur.close(); conn.close()
        return None
    except Exception as e:
        logger.warning(f"Session summary fetch failed: {e}")
        return None


def save_session_summary(employee_id: str, last_topic: str, summary: str):
    """Persist session summary to MySQL."""
    import uuid
    try:
        conn = _get_mysql_conn()
        cur = conn.cursor()
        session_id = str(uuid.uuid4())
        for tbl in ("sessions", "session_memory"):
            try:
                cur.execute(
                    f"INSERT INTO {tbl} (session_id, employee_id, last_topic, summary) "
                    f"VALUES (%s, %s, %s, %s) "
                    f"ON DUPLICATE KEY UPDATE last_topic=%s, summary=%s, updated_at=NOW()",
                    (session_id, employee_id, last_topic, summary, last_topic, summary)
                )
                conn.commit()
                break
            except Exception:
                continue
        cur.close(); conn.close()
    except Exception as e:
        logger.warning(f"Session save failed: {e}")


def get_proactive_nudges(employee_data: Dict) -> List[str]:
    """
    Generate proactive nudges for the employee based on their data.
    E.g. upcoming review, low leave balance, etc.
    """
    nudges = []
    try:
        from datetime import datetime, date
        today = date.today()

        # Performance review nudge
        perf = employee_data.get("performance", {})
        next_review = perf.get("next_review_date") or perf.get("next_review_date")
        if next_review:
            if isinstance(next_review, str):
                try:
                    next_review = date.fromisoformat(next_review[:10])
                except ValueError:
                    next_review = None
            if next_review and isinstance(next_review, date):
                days_to_review = (next_review - today).days
                if 0 <= days_to_review <= 14:
                    nudges.append(
                        f"Your performance review is scheduled in {days_to_review} day{'s' if days_to_review != 1 else ''}. "
                        f"This is a great time to review your goals and prepare your self-assessment."
                    )

        # Low annual leave nudge
        leave = employee_data.get("leave", {})
        annual_rem = leave.get("annual_remaining", leave.get("annual_remaining"))
        annual_total = leave.get("annual_total", 20)
        if annual_rem is not None:
            try:
                rem = int(annual_rem)
                tot = int(annual_total)
                if rem <= 3 and tot > 0:
                    nudges.append(
                        f"You have only {rem} day{'s' if rem != 1 else ''} of annual leave remaining. "
                        f"Please plan accordingly before the leave year ends."
                    )
            except (ValueError, TypeError):
                pass

    except Exception as e:
        logger.warning(f"Nudge generation error: {e}")
    return nudges
