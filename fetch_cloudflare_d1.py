import os
import sys
import json
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings

ACCOUNT_ID = settings.CLOUDFLARE_ACCOUNT_ID
DATABASE_ID = settings.CLOUDFLARE_D1_DATABASE_ID
API_TOKEN = settings.CLOUDFLARE_API_TOKEN

def d1_query(sql: str, params: list = None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"sql": sql}
    if params:
        payload["params"] = params
        
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                return data.get("result", [{}])[0].get("results", [])
            else:
                print(f"⚠️ D1 Query Failed: {data.get('errors')}")
                return []
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"⚠️ Cloudflare D1 HTTP Error {e.code}: {err_msg}")
        return []
    except Exception as e:
        print(f"⚠️ Cloudflare D1 Error: {e}")
        return []

def init_d1_schema():
    print("⚡ Initializing Cloudflare D1 Database Schema...")
    sql_statements = [
        """CREATE TABLE IF NOT EXISTS admins (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT 'SIH Organizer',
            role TEXT DEFAULT 'ADMIN',
            created_at TEXT
        );""",
        """CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY DEFAULT 'global_settings',
            fee REAL DEFAULT 300.0,
            currency TEXT DEFAULT 'INR',
            is_active INTEGER DEFAULT 1,
            min_members INTEGER DEFAULT 6,
            max_members INTEGER DEFAULT 6,
            female_required INTEGER DEFAULT 1,
            updated_at TEXT
        );""",
        """CREATE TABLE IF NOT EXISTS problems (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            title TEXT NOT NULL,
            organization TEXT DEFAULT '',
            category TEXT DEFAULT 'Software',
            theme TEXT DEFAULT '',
            difficulty TEXT DEFAULT 'Medium',
            description TEXT DEFAULT '',
            background TEXT DEFAULT '',
            expected_solution TEXT DEFAULT '',
            technical_requirements TEXT DEFAULT '[]',
            technologies TEXT DEFAULT '[]',
            constraint_items TEXT DEFAULT '[]',
            evaluation_criteria TEXT DEFAULT '[]',
            selected_count INTEGER DEFAULT 0,
            max_selections INTEGER DEFAULT 2,
            status TEXT DEFAULT 'AVAILABLE',
            sort_order INTEGER DEFAULT 0
        );""",
        """CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            registration_id TEXT UNIQUE NOT NULL,
            team_name TEXT UNIQUE NOT NULL,
            college TEXT NOT NULL,
            university TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            leader_name TEXT NOT NULL,
            leader_email TEXT NOT NULL,
            leader_phone TEXT NOT NULL,
            leader_gender TEXT NOT NULL,
            leader_course TEXT DEFAULT 'B.Tech',
            leader_branch TEXT DEFAULT '',
            leader_year TEXT DEFAULT '',
            leader_student_id TEXT DEFAULT '',
            registration_status TEXT DEFAULT 'CONFIRMED',
            payment_status TEXT DEFAULT 'PENDING',
            selected_problem_id TEXT,
            selected_problem_title TEXT,
            is_open_innovation INTEGER DEFAULT 0,
            open_innovation_title TEXT,
            open_innovation_description TEXT,
            registered_at TEXT,
            updated_at TEXT
        );""",
        """CREATE TABLE IF NOT EXISTS members (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            is_leader INTEGER DEFAULT 0,
            gender TEXT NOT NULL,
            college TEXT DEFAULT '',
            course TEXT DEFAULT '',
            branch TEXT DEFAULT '',
            year TEXT DEFAULT '',
            student_id TEXT DEFAULT '',
            created_at TEXT
        );""",
        """CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            registration_id TEXT NOT NULL,
            team_name TEXT NOT NULL,
            order_id TEXT NOT NULL,
            transaction_id TEXT,
            proof_key TEXT,
            proof_url TEXT,
            payment_mode TEXT DEFAULT 'ONLINE',
            collector_name TEXT,
            receipt_no TEXT,
            amount REAL DEFAULT 300.0,
            currency TEXT DEFAULT 'INR',
            status TEXT DEFAULT 'PENDING',
            admin_notes TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        );""",
        """CREATE TABLE IF NOT EXISTS expenses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            amount REAL NOT NULL,
            paid_to TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT
        );"""
    ]
    for stmt in sql_statements:
        d1_query(stmt)
    print("✅ Cloudflare D1 Schema Initialized Successfully!")

    # Seed Default Admin if missing
    admin_check = d1_query("SELECT id FROM admins WHERE email='sih@gtmcnanded.in';")
    if not admin_check:
        from app.auth import get_password_hash
        pwd_hash = get_password_hash("SihGtmc2026!")
        d1_query(
            "INSERT INTO admins (id, email, password_hash, name, role, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'));",
            ["c0cc03e4-9eed-4def-b733-26291f902386", "sih@gtmcnanded.in", pwd_hash, "SIH Organizer", "ADMIN"]
        )
        print("✅ Default Admin (sih@gtmcnanded.in) Seeded to Cloudflare D1!")

    # Seed 102 Problems if missing
    prob_check = d1_query("SELECT COUNT(*) as count FROM problems;")
    count_val = prob_check[0].get("count", 0) if prob_check else 0
    if count_val == 0:
        print("🌱 Seeding 102 Problem Statements to Cloudflare D1 Cloud...")
        json_path = os.path.join(os.path.dirname(__file__), "app", "problem_statements.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                problems_data = json.load(f)
            for idx, p in enumerate(problems_data):
                p_id = p.get("id") or p.get("code")
                d1_query(
                    """INSERT OR REPLACE INTO problems (
                        id, code, title, organization, category, theme, difficulty,
                        description, background, expected_solution, technical_requirements,
                        technologies, constraint_items, evaluation_criteria, selected_count, max_selections, status, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 2, 'AVAILABLE', ?);""",
                    [
                        p_id,
                        p.get("code", p_id),
                        p.get("title", ""),
                        p.get("organization", ""),
                        p.get("category", "Software"),
                        p.get("theme", ""),
                        p.get("difficulty", "Medium"),
                        p.get("description", ""),
                        p.get("background", ""),
                        p.get("expected_solution", ""),
                        json.dumps(p.get("technical_requirements", [])),
                        json.dumps(p.get("technologies", [])),
                        json.dumps(p.get("constraint_items", [])),
                        json.dumps(p.get("evaluation_criteria", [])),
                        idx + 1
                    ]
                )
            print(f"✅ Seeded {len(problems_data)} Problem Statements to Cloudflare D1!")

def fetch_all_d1_data():
    print("🌐 Connecting to Cloudflare D1 Cloud Database...")
    print(f"   Account ID: {ACCOUNT_ID or '(Not configured)'}")
    print(f"   Database ID: {DATABASE_ID or '(Not configured)'}")
    
    if not ACCOUNT_ID or not DATABASE_ID or not API_TOKEN:
        print("ℹ️ Cloudflare D1 credentials not fully configured in .env. Skipping D1 remote fetch.")
        return {}
    tables = d1_query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_cf_%';")
    table_names = [t["name"] for t in tables]
    print(f"📊 Cloudflare D1 Tables Found: {table_names}")

    if not table_names or "teams" not in table_names:
        print("\n⚙️ Tables missing in D1. Initializing schema now...")
        init_d1_schema()
        tables = d1_query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_cf_%';")
        table_names = [t["name"] for t in tables]

    all_data = {}
    for tbl in table_names:
        rows = d1_query(f"SELECT * FROM {tbl};")
        all_data[tbl] = rows
        print(f"   🔹 Table '{tbl}': {len(rows)} records found in Cloudflare D1 cloud")

    # Export to JSON
    export_filename = "cloudflare_d1_export.json"
    with open(export_filename, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)

    print(f"\n✅ All Cloudflare D1 Cloud Data successfully fetched and saved to '{export_filename}'!")
    return all_data

if __name__ == "__main__":
    fetch_all_d1_data()
