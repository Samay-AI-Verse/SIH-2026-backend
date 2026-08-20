import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Team, Problem
from app.d1_client import CloudflareD1Client
from app.d1_sync import sync_team_to_d1, sync_problem_to_d1

def assign_sample_problems():
    print("🚀 Assigning Problem Statements & Open Innovation to 10 Real Teams...")
    db = SessionLocal()
    d1 = CloudflareD1Client()

    teams = db.query(Team).order_by(Team.registered_at.asc()).all()
    problems = db.query(Problem).filter(Problem.id != "OPEN_INNOVATION").order_by(Problem.sort_order.asc()).all()

    if len(teams) == 0:
        print("⚠️ No teams found in database.")
        db.close()
        return

    print(f"📌 Found {len(teams)} teams and {len(problems)} problem statements.")

    # List of allocations
    # Team 1: Open Innovation
    # Teams 2-10: Problem Statements (SIH12507, SIH12508, SIH25001, SIH25002, etc.)
    
    for idx, team in enumerate(teams):
        if idx == 0:
            # Open Innovation
            team.is_open_innovation = True
            team.selected_problem_id = "OPEN_INNOVATION"
            team.selected_problem_title = "AI-Driven Smart Agriculture & Pest Crop Yield Monitoring System"
            team.open_innovation_title = "AI-Driven Smart Agriculture & Pest Crop Yield Monitoring System"
            team.open_innovation_description = "A deep learning & IoT solution for real-time crop disease detection and automated pesticide spraying drones."
            open_prob = db.query(Problem).filter(Problem.id == "OPEN_INNOVATION").first()
            if open_prob:
                open_prob.selected_count += 1
                sync_problem_to_d1(open_prob)
            print(f"   ↳ Team '{team.team_name}': Assigned Open Innovation")
        else:
            prob = problems[(idx - 1) % len(problems)]
            team.is_open_innovation = False
            team.selected_problem_id = prob.id
            team.selected_problem_title = prob.title
            team.open_innovation_title = None
            team.open_innovation_description = None
            prob.selected_count += 1
            if prob.selected_count >= prob.max_selections:
                prob.status = "LOCKED"
            sync_problem_to_d1(prob)
            print(f"   ↳ Team '{team.team_name}': Assigned Problem Statement '{prob.code}' - {prob.title[:30]}...")

        sync_team_to_d1(team)

    db.commit()

    if d1.is_configured():
        print("🌐 Syncing team problem statement allocations directly to Cloudflare D1 Cloud...")
        for team in teams:
            sql = """UPDATE teams SET 
                selected_problem_id = ?,
                selected_problem_title = ?,
                is_open_innovation = ?,
                open_innovation_title = ?,
                open_innovation_description = ?
            WHERE id = ? OR registration_id = ?;"""
            params = [
                team.selected_problem_id,
                team.selected_problem_title,
                1 if team.is_open_innovation else 0,
                team.open_innovation_title,
                team.open_innovation_description,
                str(team.id),
                str(team.registration_id)
            ]
            try:
                d1.query(sql, params)
            except Exception as e:
                print(f"⚠️ D1 update notice for team {team.team_name}:", e)

    print("🎉 Problem Statement Allocation Complete!")
    db.close()

if __name__ == "__main__":
    assign_sample_problems()
