import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Team, Member, Payment, Problem
from app.d1_client import CloudflareD1Client

def fix_and_resync():
    print("🚀 Starting Orphan Data Purge & Database Resynchronization...")
    d1 = CloudflareD1Client()
    db = SessionLocal()

    if d1.is_configured():
        print("🌐 1. Purging orphan members & payments from Cloudflare D1 Cloud...")
        try:
            # Delete orphan members from D1 whose team_id is not in teams
            del_m_res = d1.query("DELETE FROM members WHERE team_id NOT IN (SELECT id FROM teams);")
            print("   ↳ Purged orphan members from Cloudflare D1:", del_m_res)

            # Delete orphan payments from D1
            del_p_res = d1.query("DELETE FROM payments WHERE team_id NOT IN (SELECT id FROM teams);")
            print("   ↳ Purged orphan payments from Cloudflare D1:", del_p_res)

            # Fetch active teams & members from D1
            teams_res = d1.query("SELECT * FROM teams;")
            teams_rows = teams_res.get("results", []) if isinstance(teams_res, dict) else (teams_res or [])
            
            members_res = d1.query("SELECT * FROM members;")
            members_rows = members_res.get("results", []) if isinstance(members_res, dict) else (members_res or [])

            payments_res = d1.query("SELECT * FROM payments;")
            payments_rows = payments_res.get("results", []) if isinstance(payments_res, dict) else (payments_res or [])

            print(f"📊 Clean D1 State: {len(teams_rows)} Teams, {len(members_rows)} Members, {len(payments_rows)} Payments")
        except Exception as e:
            print("⚠️ Error querying Cloudflare D1:", e)
            return

    # 2. Resync local SQLite sih_2026.db
    print("💾 2. Syncing local SQLite database (sih_2026.db)...")
    
    # Purge local SQLite tables to re-populate from clean D1 state
    db.query(Member).delete(synchronize_session=False)
    db.query(Payment).delete(synchronize_session=False)
    db.query(Team).delete(synchronize_session=False)
    db.commit()

    # Re-insert teams from D1
    for row in teams_rows:
        new_t = Team(
            id=str(row["id"]),
            registration_id=str(row.get("registration_id", "")),
            team_name=str(row.get("team_name", "")),
            college=str(row.get("college", "")),
            university=str(row.get("university", "")),
            city=str(row.get("city", "")),
            state=str(row.get("state", "")),
            leader_name=str(row.get("leader_name", "")),
            leader_email=str(row.get("leader_email", "")),
            leader_phone=str(row.get("leader_phone", "")),
            leader_gender=str(row.get("leader_gender", "")),
            leader_course=str(row.get("leader_course", "B.Tech")),
            leader_branch=str(row.get("leader_branch", "")),
            leader_year=str(row.get("leader_year", "")),
            leader_student_id=str(row.get("leader_student_id", "")),
            registration_status=str(row.get("registration_status", "CONFIRMED")),
            payment_status=str(row.get("payment_status", "SUCCESS")),
            selected_problem_id=row.get("selected_problem_id"),
            selected_problem_title=row.get("selected_problem_title"),
            is_open_innovation=bool(row.get("is_open_innovation", 0)),
            open_innovation_title=row.get("open_innovation_title"),
            open_innovation_description=row.get("open_innovation_description"),
            registered_at=str(row.get("registered_at", "")),
            updated_at=str(row.get("updated_at", ""))
        )
        db.add(new_t)
    db.commit()

    # Re-insert members from D1
    for row in members_rows:
        new_m = Member(
            id=str(row["id"]),
            team_id=str(row.get("team_id", "")),
            full_name=str(row.get("full_name", "")),
            email=str(row.get("email", "")),
            phone=str(row.get("phone", "")),
            is_leader=bool(row.get("is_leader", 0)),
            gender=str(row.get("gender", "")),
            college=str(row.get("college", "")),
            course=str(row.get("course", "")),
            branch=str(row.get("branch", "")),
            year=str(row.get("year", "")),
            student_id=str(row.get("student_id", "")),
            created_at=str(row.get("created_at", ""))
        )
        db.add(new_m)
    db.commit()

    # Re-insert payments from D1
    for row in payments_rows:
        new_p = Payment(
            id=str(row["id"]),
            team_id=str(row.get("team_id", "")),
            registration_id=str(row.get("registration_id", "")),
            team_name=str(row.get("team_name", "")),
            order_id=str(row.get("order_id", f"ORD-{row['id'][:8]}")),
            transaction_id=row.get("transaction_id"),
            proof_key=row.get("proof_key"),
            proof_url=row.get("proof_url"),
            payment_mode=str(row.get("payment_mode", "ONLINE")),
            collector_name=row.get("collector_name"),
            receipt_no=row.get("receipt_no"),
            amount=float(row.get("amount", 300.0)),
            currency=str(row.get("currency", "INR")),
            status=str(row.get("status", "SUCCESS")),
            admin_notes=str(row.get("admin_notes", "")),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", ""))
        )
        db.add(new_p)
    db.commit()

    # Final count verification
    local_teams = db.query(Team).count()
    local_members = db.query(Member).count()
    local_payments = db.query(Payment).count()

    print(f"🎉 Resync Complete! Local SQLite now has {local_teams} Teams, {local_members} Members, {local_payments} Payments.")
    db.close()

if __name__ == "__main__":
    fix_and_resync()
