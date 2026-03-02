#!/usr/bin/env python3
"""
NovaCorp HR AI - Setup & Seed Script
Run once after installation.

Steps:
  1. Check Python dependencies
  2. Check Ollama availability
  3. Create required directories
  4. Seed MySQL with demo employee data
  5. Index knowledge base into ChromaDB
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


def banner():
    print("""
+--------------------------------------------------------------+
|         NovaCorp HR AI Assistant  --  Setup & Seed           |
+--------------------------------------------------------------+
    """)


def check_dependencies():
    logger.info("Checking Python dependencies...")
    required = [
        ("faiss",                 "faiss-cpu"),
        ("sentence_transformers", "sentence-transformers"),
        ("fastapi",               "fastapi"),
        ("uvicorn",               "uvicorn[standard]"),
        ("httpx",                 "httpx"),
    ]
    optional = [
        ("pypdf",         "pypdf"),
        ("docx",          "python-docx"),
        ("mysql.connector","mysql-connector-python"),
    ]
    missing = []
    for module, pkg in required:
        try:
            __import__(module)
            logger.info(f"  OK  {pkg}")
        except ImportError:
            logger.error(f"  ERR {pkg}  (REQUIRED)")
            missing.append(pkg)
    for module, pkg in optional:
        try:
            __import__(module)
            logger.info(f"  OK  {pkg}")
        except ImportError:
            logger.warning(f"  --  {pkg}  (optional)")
    if missing:
        logger.error(f"\nInstall missing packages: pip install {' '.join(missing)}")
        sys.exit(1)
    logger.info("All required dependencies present.\n")


def check_ollama():
    logger.info("Checking Ollama...")
    try:
        from backend.llm.ollama_client import check_ollama_available
        if check_ollama_available():
            logger.info("  Ollama is running.")
        else:
            logger.warning("  Ollama is NOT running. System will use demo mock responses.")
            logger.warning("  To enable full AI: install Ollama, then run: ollama pull mistral")
    except Exception as e:
        logger.warning(f"  Could not check Ollama: {e}")


def create_directories():
    logger.info("Creating directory structure...")
    from config.settings import KB_CATEGORIES, VECTOR_DB_DIR, EMPLOYEE_DATA_DIR
    dirs = list(KB_CATEGORIES.values()) + [VECTOR_DB_DIR, EMPLOYEE_DATA_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.info(f"  {d}")
    logger.info("")


def seed_mysql():
    """
    Seed MySQL with demo employee data.
    Uses the same schema as database/setup_mysql.py (create_novacorp_db.py variant).
    """
    logger.info("Seeding MySQL database...")
    try:
        import mysql.connector
        from config.settings import (
            MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
            MYSQL_DATABASE, MYSQL_AUTH_PLUGIN
        )
    except ImportError:
        logger.warning("  mysql-connector-python not installed. Skipping MySQL seed.")
        logger.warning("  Run: pip install mysql-connector-python")
        return

    # ── Schema ────────────────────────────────────────────────────────────────
    TABLES = {}
    TABLES["employees"] = """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id   VARCHAR(20)   NOT NULL PRIMARY KEY,
            pin           VARCHAR(10)   NOT NULL,
            name          VARCHAR(100)  NOT NULL,
            department    VARCHAR(100),
            role          VARCHAR(100),
            grade         VARCHAR(20),
            manager       VARCHAR(100),
            join_date     DATE,
            email         VARCHAR(150),
            phone         VARCHAR(30)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["leave_balances"] = """
        CREATE TABLE IF NOT EXISTS leave_balances (
            employee_id          VARCHAR(20) NOT NULL PRIMARY KEY,
            annual_total         INT         NOT NULL DEFAULT 20,
            annual_used          INT         NOT NULL DEFAULT 0,
            annual_remaining     INT         NOT NULL DEFAULT 20,
            sick_total           INT         NOT NULL DEFAULT 10,
            sick_used            INT         NOT NULL DEFAULT 0,
            sick_remaining       INT         NOT NULL DEFAULT 10,
            casual_total         INT         NOT NULL DEFAULT 5,
            casual_used          INT         NOT NULL DEFAULT 0,
            casual_remaining     INT         NOT NULL DEFAULT 5,
            maternity_available  TINYINT(1)  NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["salary"] = """
        CREATE TABLE IF NOT EXISTS salary (
            employee_id          VARCHAR(20)    NOT NULL PRIMARY KEY,
            base_salary          DECIMAL(12,2)  NOT NULL,
            currency             VARCHAR(10)    NOT NULL DEFAULT 'USD',
            pay_frequency        VARCHAR(20)    NOT NULL DEFAULT 'Monthly',
            last_increment_date  DATE,
            last_increment_pct   DECIMAL(5,2),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["incentives"] = """
        CREATE TABLE IF NOT EXISTS incentives (
            employee_id                VARCHAR(20)    NOT NULL PRIMARY KEY,
            annual_bonus_target_pct    DECIMAL(5,2)   NOT NULL DEFAULT 0,
            last_bonus_paid            DECIMAL(12,2)  NOT NULL DEFAULT 0,
            stock_options              INT            NOT NULL DEFAULT 0,
            referral_bonus_available   DECIMAL(10,2)  NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["benefits"] = """
        CREATE TABLE IF NOT EXISTS benefits (
            employee_id           VARCHAR(20)    NOT NULL PRIMARY KEY,
            health_insurance      VARCHAR(100),
            dental                TINYINT(1)     NOT NULL DEFAULT 0,
            vision                TINYINT(1)     NOT NULL DEFAULT 0,
            match_401k_pct        DECIMAL(5,2)   NOT NULL DEFAULT 0,
            life_insurance        VARCHAR(100),
            remote_work_stipend   DECIMAL(10,2)  NOT NULL DEFAULT 0,
            learning_budget       DECIMAL(10,2)  NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["performance"] = """
        CREATE TABLE IF NOT EXISTS performance (
            employee_id        VARCHAR(20)   NOT NULL PRIMARY KEY,
            last_review_score  DECIMAL(3,2),
            last_review_date   DATE,
            next_review_date   DATE,
            current_cycle      VARCHAR(50),
            goals_completed    INT           NOT NULL DEFAULT 0,
            goals_total        INT           NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    TABLES["sessions"] = """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    VARCHAR(64)  NOT NULL PRIMARY KEY,
            employee_id   VARCHAR(20),
            last_topic    VARCHAR(50),
            summary       TEXT,
            updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    # ── Demo data ─────────────────────────────────────────────────────────────
    EMPLOYEES = [
        ("EMP001","1234","Alice Johnson",  "Engineering","Senior Software Engineer","L5","David Chen",  "2021-03-15","alice.johnson@novacorp.com",  "+1-555-0101"),
        ("EMP002","5678","Brian Martinez", "Marketing",  "Marketing Manager",       "L4","Sarah Kim",   "2020-07-20","brian.martinez@novacorp.com", "+1-555-0102"),
        ("EMP003","9012","Carol White",    "HR",         "HR Business Partner",     "L3","Janet Lee",   "2022-01-10","carol.white@novacorp.com",    "+1-555-0103"),
        ("EMP004","3456","David Chen",     "Engineering","Engineering Director",    "L7","Emma Walsh",  "2018-06-01","david.chen@novacorp.com",     "+1-555-0104"),
        ("EMP005","7890","Priya Sharma",   "Finance",    "Financial Analyst",       "L3","Mark Benson", "2023-02-14","priya.sharma@novacorp.com",   "+1-555-0105"),
    ]
    LEAVE = [
        ("EMP001", 20,  7, 13, 10, 2,  8, 5, 1, 4, 1),
        ("EMP002", 20, 14,  6, 10, 5,  5, 5, 3, 2, 0),
        ("EMP003", 20,  3, 17, 10, 0, 10, 5, 2, 3, 1),
        ("EMP004", 25, 10, 15, 12, 1, 11, 5, 0, 5, 0),
        ("EMP005", 20,  2, 18, 10, 1,  9, 5, 0, 5, 1),
    ]
    SALARY = [
        ("EMP001",  95000.00,"USD","Monthly","2024-01-01",12.5),
        ("EMP002",  82000.00,"USD","Monthly","2024-01-01",10.0),
        ("EMP003",  68000.00,"USD","Monthly","2024-01-01", 8.0),
        ("EMP004",145000.00,"USD","Monthly","2024-01-01",15.0),
        ("EMP005",  72000.00,"USD","Monthly","2024-01-01", 9.0),
    ]
    INCENTIVES = [
        ("EMP001",15.0,12500.00, 500,3000.00),
        ("EMP002",12.0, 9000.00, 250,3000.00),
        ("EMP003",10.0, 6000.00, 100,3000.00),
        ("EMP004",20.0,27000.00,1500,5000.00),
        ("EMP005",10.0, 6500.00, 100,3000.00),
    ]
    BENEFITS = [
        ("EMP001","Premium Plan (Family)",      1,1,5.0,"2x salary",1200.00,2000.00),
        ("EMP002","Standard Plan (Individual)", 1,0,5.0,"2x salary", 800.00,1500.00),
        ("EMP003","Standard Plan (Family)",     1,1,5.0,"2x salary", 600.00,1500.00),
        ("EMP004","Executive Plan (Family)",    1,1,6.0,"3x salary",2000.00,5000.00),
        ("EMP005","Standard Plan (Individual)", 1,0,5.0,"2x salary", 800.00,1500.00),
    ]
    PERFORMANCE = [
        ("EMP001",4.2,"2023-12-15","2024-06-15","2024 Mid-Year Review",3,5),
        ("EMP002",3.8,"2023-12-15","2024-06-15","2024 Mid-Year Review",4,6),
        ("EMP003",4.0,"2023-12-15","2024-06-15","2024 Mid-Year Review",2,4),
        ("EMP004",4.5,"2023-12-15","2024-06-15","2024 Mid-Year Review",5,6),
        ("EMP005",3.6,"2023-12-15","2024-06-15","2024 Mid-Year Review",1,3),
    ]

    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            connection_timeout=5,
            auth_plugin=MYSQL_AUTH_PLUGIN,
            use_pure=True,
        )
        cur = conn.cursor()
        logger.info(f"  Connected to MySQL at {MYSQL_HOST}:{MYSQL_PORT} / {MYSQL_DATABASE}")
    except Exception as e:
        logger.error(f"  Could not connect to MySQL: {e}")
        logger.error("  Please create the database and user first:")
        logger.error("    CREATE DATABASE novacorp_hr;")
        logger.error("    CREATE USER 'novacorp_user'@'%' IDENTIFIED WITH mysql_native_password BY 'novacorp_pass';")
        logger.error("    GRANT ALL PRIVILEGES ON novacorp_hr.* TO 'novacorp_user'@'%';")
        logger.error("    FLUSH PRIVILEGES;")
        logger.warning("  Continuing without MySQL — system will use JSON fallback.")
        return

    # Create tables
    for name, ddl in TABLES.items():
        try:
            cur.execute(ddl)
            logger.info(f"  Table '{name}' ready.")
        except Exception as e:
            logger.error(f"  Table '{name}' failed: {e}")

    # Insert employees (ON DUPLICATE KEY UPDATE = safe to re-run)
    for row in EMPLOYEES:
        cur.execute("""
            INSERT INTO employees
              (employee_id,pin,name,department,role,grade,manager,join_date,email,phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              name=VALUES(name),department=VALUES(department),
              role=VALUES(role),grade=VALUES(grade),manager=VALUES(manager),email=VALUES(email)
        """, row)
    for row in LEAVE:
        cur.execute("""
            INSERT INTO leave_balances
              (employee_id,annual_total,annual_used,annual_remaining,
               sick_total,sick_used,sick_remaining,
               casual_total,casual_used,casual_remaining,maternity_available)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              annual_used=VALUES(annual_used),annual_remaining=VALUES(annual_remaining),
              sick_used=VALUES(sick_used),sick_remaining=VALUES(sick_remaining)
        """, row)
    for row in SALARY:
        cur.execute("""
            INSERT INTO salary
              (employee_id,base_salary,currency,pay_frequency,last_increment_date,last_increment_pct)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              base_salary=VALUES(base_salary),last_increment_pct=VALUES(last_increment_pct)
        """, row)
    for row in INCENTIVES:
        cur.execute("""
            INSERT INTO incentives
              (employee_id,annual_bonus_target_pct,last_bonus_paid,
               stock_options,referral_bonus_available)
            VALUES (%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              annual_bonus_target_pct=VALUES(annual_bonus_target_pct),
              last_bonus_paid=VALUES(last_bonus_paid)
        """, row)
    for row in BENEFITS:
        cur.execute("""
            INSERT INTO benefits
              (employee_id,health_insurance,dental,vision,
               match_401k_pct,life_insurance,remote_work_stipend,learning_budget)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              health_insurance=VALUES(health_insurance),
              dental=VALUES(dental),vision=VALUES(vision),
              learning_budget=VALUES(learning_budget)
        """, row)
    for row in PERFORMANCE:
        cur.execute("""
            INSERT INTO performance
              (employee_id,last_review_score,last_review_date,
               next_review_date,current_cycle,goals_completed,goals_total)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              last_review_score=VALUES(last_review_score),
              next_review_date=VALUES(next_review_date),
              goals_completed=VALUES(goals_completed),goals_total=VALUES(goals_total)
        """, row)

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"  {len(EMPLOYEES)} employees seeded into MySQL.\n")

    logger.info("  Demo Employee Credentials:")
    logger.info("  " + "-"*50)
    logger.info(f"  {'ID':<10} {'PIN':<8} {'Name':<22} {'Dept'}")
    logger.info("  " + "-"*50)
    for emp in EMPLOYEES:
        logger.info(f"  {emp[0]:<10} {emp[1]:<8} {emp[2]:<22} {emp[3]}")
    logger.info("")


def run_initial_index():
    logger.info("Indexing seed knowledge base into ChromaDB...")
    from backend.ingestion.pipeline import ingest_all
    result = ingest_all(reset=True)
    logger.info(f"  Files indexed : {result['total_files']}")
    logger.info(f"  Total chunks  : {result['total_chunks']:,}")
    logger.info("")
    for r in result["results"]:
        status = "OK " if r["status"] == "ok" else "ERR"
        logger.info(f"  {status}  {r['file']} ({r['category']}) -> {r['chunks']} chunks")


def print_launch_info():
    print("""
+--------------------------------------------------------------+
|                   Setup Complete                             |
+--------------------------------------------------------------+
|  Launch both servers:                                        |
|  $ python -m scripts.launch_all                              |
|                                                              |
|  Admin Console:    http://localhost:7860                     |
|  Employee Portal:  http://localhost:7861                     |
|                                                              |
|  Employee logins:  EMP001/1234  EMP002/5678  EMP003/9012    |
|                    EMP004/3456  EMP005/7890                  |
|  Admin login:      admin / novacorp@admin2024                |
|                                                              |
|  Optional -- Enable Full AI:                                 |
|  1. Install Ollama: https://ollama.com                       |
|  2. ollama pull mistral                                      |
|  3. ollama serve                                             |
+--------------------------------------------------------------+
    """)


if __name__ == "__main__":
    banner()
    check_dependencies()
    check_ollama()
    create_directories()
    seed_mysql()
    run_initial_index()
    print_launch_info()
