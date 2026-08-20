import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Team, Problem
from app.d1_client import CloudflareD1Client
from app.d1_sync import sync_team_to_d1, sync_problem_to_d1

def reset_selections():
    print("🧹 Resetting all team problem statement selections back to 'Not Selected Yet'...")
    db = SessionLocal()
    d1 = CloudflareD1Client()

    teams = db.query(Team).all()
    problems = db.query(Problem).all()

    # Reset all teams
    for team in teams:
        team.selected_problem_id = None
        team.selected_problem_title = None
        team.is_open_innovation = False
        team.open_innovation_title = None
        team.open_innovation_description = None
        sync_team_to_d1(team)

    # Reset all problems count
    for prob in problems:
        prob.selected_count = 0
        prob.status = "AVAILABLE"
        sync_problem_to_d1(prob)

    db.commit()

    # Reset Cloudflare D1 Cloud
    if d1.is_configured():
        print("🌐 Resetting Cloudflare D1 Cloud problem selections...")
        try:
            d1.query("UPDATE teams SET selected_problem_id = NULL, selected_problem_title = NULL, is_open_innovation = 0, open_innovation_title = NULL, open_innovation_description = NULL;")
            d1.query("UPDATE problems SET selected_count = 0, status = 'AVAILABLE';")
            print("✅ Cloudflare D1 Cloud reset complete!")
        except Exception as e:
            print("⚠️ Notice resetting D1 Cloud:", e)

    print("🎉 All 10 teams reset to 'Not Selected Yet' (0 Allocated).")
    db.close()

if __name__ == "__main__":
    reset_selections()
