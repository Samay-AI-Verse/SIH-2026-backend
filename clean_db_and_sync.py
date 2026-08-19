import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Team, Member, Payment, Problem
from app.d1_client import CloudflareD1Client

def clean_database():
    print("🧹 Starting complete database & Cloudflare D1 cleanup script...")
    db = SessionLocal()
    d1 = CloudflareD1Client()
    
    # 1. Fetch existing teams
    teams = db.query(Team).all()
    print(f"📌 Found {len(teams)} teams in local SQLite DB.")

    # Reset selected count on problem statements
    for team in teams:
        if team.selected_problem_id:
            prob = db.query(Problem).filter(Problem.id == team.selected_problem_id).first()
            if prob:
                prob.selected_count = max(0, prob.selected_count - 1)
                if prob.selected_count < prob.max_selections:
                    prob.status = "AVAILABLE"
                print(f"   ↳ Reset problem quota for {prob.id} ({prob.code}): selected_count = {prob.selected_count}")

    # Delete all members, payments, teams from local DB
    num_members = db.query(Member).delete(synchronize_session=False)
    num_payments = db.query(Payment).delete(synchronize_session=False)
    num_teams = db.query(Team).delete(synchronize_session=False)
    
    # Reset all problems to available if count is 0
    problems = db.query(Problem).all()
    for p in problems:
        if p.selected_count <= 0:
            p.selected_count = 0
            p.status = "AVAILABLE"

    db.commit()
    print(f"✅ Local SQLite Purge: Deleted {num_teams} teams, {num_members} members, {num_payments} payments.")

    # 2. Hard Delete from Cloudflare D1 Cloud
    if d1.is_configured():
        print("🌐 Executing Cloudflare D1 Cloud hard purge...")
        try:
            d1.query("DELETE FROM members;")
            d1.query("DELETE FROM payments;")
            d1.query("DELETE FROM teams;")
            d1.query("UPDATE problems SET selected_count = 0, status = 'AVAILABLE';")
            print("🎉 Cloudflare D1 Cloud Database successfully purged and problem quotas reset!")
        except Exception as e:
            print("⚠️ Cloudflare D1 Purge Notice:", e)
    else:
        print("ℹ️ Cloudflare D1 credentials not configured in .env, skipped D1 remote query.")

    # 3. Clean up any duplicate SQLite files in SIH-Frontend if present
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_db = os.path.join(base_dir, "SIH-Frontend", "sih_2026.db")
    if os.path.exists(frontend_db):
        try:
            import sqlite3
            conn = sqlite3.connect(frontend_db)
            cur = conn.cursor()
            cur.execute("DELETE FROM members;")
            cur.execute("DELETE FROM payments;")
            cur.execute("DELETE FROM teams;")
            conn.commit()
            conn.close()
            os.remove(frontend_db)
            print(f"🧹 Removed legacy frontend database file: {frontend_db}")
        except Exception as e:
            print("⚠️ Notice removing frontend DB file:", e)

    db.close()

if __name__ == "__main__":
    clean_database()
