import sys
from app.database import SessionLocal
from app.models import Team, Payment, Member
from app.d1_sync import sync_team_to_d1

def migrate_registration_ids():
    db = SessionLocal()
    try:
        teams = db.query(Team).all()
        if not teams:
            print("No teams found in database.")
            return

        counts = {
            "DIPLOMA-SIH": 0,
            "ENGG-SIH": 0,
            "PHARMA-SIH": 0,
            "BSC-SIH": 0
        }

        print(f"Migrating {len(teams)} teams to stream-based registration IDs...")
        for team in teams:
            leader = db.query(Member).filter(Member.team_id == team.id, Member.is_leader == True).first()
            course = (leader.course if leader else team.leader_course) or ""
            branch = (leader.branch if leader else team.leader_branch) or ""
            combined = f"{course} {branch}".lower().strip()

            if "diploma" in combined or "poly" in combined:
                prefix = "DIPLOMA-SIH"
            elif "pharm" in combined:
                prefix = "PHARMA-SIH"
            elif "b.sc" in combined or "m.sc" in combined or "science" in combined:
                prefix = "BSC-SIH"
            else:
                prefix = "ENGG-SIH"

            counts[prefix] += 1
            new_reg_id = f"{prefix}-{counts[prefix]:02d}"

            old_reg_id = team.registration_id
            team.registration_id = new_reg_id

            # Update Payment registration_id
            payments = db.query(Payment).filter(Payment.team_id == team.id).all()
            for p in payments:
                p.registration_id = new_reg_id

            print(f"  Team '{team.team_name}': {old_reg_id} -> {new_reg_id}")
            sync_team_to_d1(team)

        db.commit()
        print("Migration completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate_registration_ids()
