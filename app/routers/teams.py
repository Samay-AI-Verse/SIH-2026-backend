import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Team, Member, Problem, Payment, Setting
from ..schemas import TeamRegisterRequest, TeamOut, MemberOut
from ..r2_storage import generate_presigned_download_url

router = APIRouter(prefix="/api", tags=["Teams"])

def generate_registration_id(db: Session, course: str = "", branch: str = "") -> str:
    combined = f"{course} {branch}".lower().strip()
    if "diploma" in combined or "poly" in combined:
        prefix = "DIPLOMA-SIH"
    elif "pharm" in combined:
        prefix = "PHARMA-SIH"
    elif "b.sc" in combined or "m.sc" in combined or "science" in combined:
        prefix = "BSC-SIH"
    else:
        prefix = "ENGG-SIH"

    existing_ids = set(
        r[0] for r in db.query(Team.registration_id).filter(Team.registration_id.like(f"{prefix}-%")).all() if r[0]
    )
    counter = 1
    while f"{prefix}-{counter:02d}" in existing_ids:
        counter += 1
    return f"{prefix}-{counter:02d}"

@router.post("/register")
def register_team(req: TeamRegisterRequest, db: Session = Depends(get_db)):
    # 0. Check if registrations are currently open
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    if setting and setting.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team registrations are currently closed by the organizing committee. Please contact the administrator."
        )

    team_name_clean = req.team_name.strip()
    leader_email_clean = req.leader_email.strip().lower()
    
    # 1. Strict Duplicate Team Name Check (Case-insensitive)
    existing_team = db.query(Team).filter(
        func.lower(Team.team_name) == func.lower(team_name_clean)
    ).first()
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team name '{team_name_clean}' is already registered. Please choose a different unique team name."
        )

    # 1b. Duplicate Leader Email Check
    existing_leader = db.query(Team).filter(
        func.lower(Team.leader_email) == leader_email_clean
    ).first()
    if existing_leader:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leader email '{leader_email_clean}' is already registered with team '{existing_leader.team_name}'."
        )


    # 2. Handle Problem Selection if selected at registration
    problem_title = None
    if req.selected_problem_id:
        problem = db.query(Problem).filter(Problem.id == req.selected_problem_id).first()
        if not problem:
            raise HTTPException(status_code=404, detail="Selected problem statement not found")
        
        # Check max 2 teams limit (except Open Innovation)
        is_open = problem.id == "OPEN_INNOVATION" or problem.category == "Open Innovation"
        if not is_open and problem.selected_count >= problem.max_selections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This problem statement has already reached its maximum quota of 2 teams. Please select another problem statement or choose Open Innovation."
            )
        problem_title = problem.title
        problem.selected_count += 1
        if not is_open and problem.selected_count >= problem.max_selections:
            problem.status = "LOCKED"

    # 4. Create Team Record with Stream Prefix (ENGG-SIH-01 / DIPLOMA-SIH-01)
    reg_id = generate_registration_id(db, course=req.leader_course or "", branch=req.leader_branch or "")
    team = Team(
        registration_id=reg_id,
        team_name=team_name_clean,
        college=req.college.strip(),
        university=req.university.strip() if req.university else req.college.strip(),
        city=req.city.strip(),
        state=req.state.strip(),
        leader_name=req.leader_name.strip(),
        leader_email=leader_email_clean,
        leader_phone=req.leader_phone.strip(),
        leader_gender=req.leader_gender,
        leader_course=req.leader_course or "",
        leader_branch=req.leader_branch or "",
        leader_year=req.leader_year or "",
        leader_student_id=req.leader_student_id or "",
        registration_status="PENDING_PAYMENT",
        payment_status="PENDING",
        selected_problem_id=req.selected_problem_id,
        selected_problem_title=problem_title,
        is_open_innovation=req.is_open_innovation or (req.selected_problem_id == "OPEN_INNOVATION"),
        open_innovation_title=req.open_innovation_title,
        open_innovation_description=req.open_innovation_description
    )
    db.add(team)
    db.flush() # Populate team.id

    # 5. Insert Members (Leader + 5 Members)
    for idx, m in enumerate(req.members):
        is_ldr = (idx == 0) or (m.email.strip().lower() == leader_email_clean)
        member = Member(
            team_id=team.id,
            is_leader=is_ldr,
            full_name=m.full_name.strip(),
            email=m.email.strip().lower() if m.email else (leader_email_clean if is_ldr else ""),
            phone=m.phone.strip() if m.phone else (req.leader_phone.strip() if is_ldr else ""),
            gender=m.gender,
            college=m.college.strip() if m.college else req.college.strip(),
            course=m.course.strip() if m.course else (req.leader_course or ""),
            branch=m.branch.strip() if m.branch else (req.leader_branch or ""),
            year=m.year.strip() if m.year else (req.leader_year or ""),
            student_id=m.student_id.strip() if m.student_id else (req.leader_student_id if is_ldr else "")
        )
        db.add(member)

    # 6. Create Initial Payment Record
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    fee = setting.fee if setting else 300.0
    currency = setting.currency if setting else "INR"
    order_id = f"ORDER-{reg_id}-{uuid.uuid4().hex[:6].upper()}"
    
    payment = Payment(
        team_id=team.id,
        registration_id=reg_id,
        team_name=team_name_clean,
        order_id=order_id,
        amount=fee,
        currency=currency,
        status="PENDING"
    )
    db.add(payment)
    db.commit()

    return {
        "success": True,
        "team_id": team.id,
        "registration_id": team.registration_id,
        "team_name": team.team_name,
        "order_id": order_id,
        "fee": fee,
        "currency": currency,
        "message": "Team registration successful! Please proceed with payment verification."
    }

@router.get("/teams/{team_id}")
def get_team_details(team_id: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        # Check by registration_id
        team = db.query(Team).filter(Team.registration_id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    payment = db.query(Payment).filter(Payment.team_id == team.id).order_by(Payment.created_at.desc()).first()
    proof_url = None
    if payment and payment.proof_key:
        proof_url = generate_presigned_download_url(payment.proof_key)
    elif payment and payment.proof_url:
        proof_url = payment.proof_url

    members_list = [
        {
            "id": m.id,
            "team_id": m.team_id,
            "is_leader": m.is_leader,
            "name": m.full_name,
            "full_name": m.full_name,
            "email": m.email,
            "phone": m.phone,
            "gender": m.gender,
            "college": m.college,
            "course": m.course,
            "branch": m.branch,
            "year": m.year,
            "student_id": m.student_id,
            "created_at": m.created_at
        }
        for m in team.members
    ]

    return {
        "team": {
            "id": team.id,
            "registration_id": team.registration_id,
            "registrationId": team.registration_id,
            "team_name": team.team_name,
            "teamName": team.team_name,
            "college": team.college,
            "university": team.university,
            "city": team.city,
            "state": team.state,
            "leader_name": team.leader_name,
            "leaderName": team.leader_name,
            "leader_email": team.leader_email,
            "leaderEmail": team.leader_email,
            "email": team.leader_email,
            "leader_phone": team.leader_phone,
            "leaderPhone": team.leader_phone,
            "phone": team.leader_phone,
            "leader_gender": team.leader_gender,
            "registration_status": team.registration_status,
            "registrationStatus": team.registration_status,
            "payment_status": team.payment_status,
            "paymentStatus": team.payment_status,
            "selected_problem_id": team.selected_problem_id,
            "selectedProblemId": team.selected_problem_id,
            "selected_problem_title": team.selected_problem_title,
            "selectedProblemTitle": team.selected_problem_title,
            "is_open_innovation": team.is_open_innovation,
            "open_innovation_title": team.open_innovation_title,
            "open_innovation_description": team.open_innovation_description,
            "registered_at": team.registered_at,
            "payment_utr": payment.transaction_id if payment else None,
            "payment_proof_url": proof_url,
            "payment_order_id": payment.order_id if payment else None
        },
        "members": members_list
    }

@router.put("/teams/{team_id}/members/{member_id}")

def update_team_member(team_id: str, member_id: str, payload: dict, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        team = db.query(Team).filter(Team.registration_id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    member = db.query(Member).filter(Member.id == member_id, Member.team_id == team.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found for this team")

    full_name_input = payload.get("full_name") or payload.get("name")
    if full_name_input and full_name_input.strip():
        member.full_name = full_name_input.strip()

    if "email" in payload and payload["email"]:
        member.email = payload["email"].strip().lower()
    if "phone" in payload and payload["phone"]:
        member.phone = payload["phone"].strip()
    if "gender" in payload and payload["gender"]:
        member.gender = payload["gender"]
    if "course" in payload and payload["course"]:
        member.course = payload["course"].strip()
    if "branch" in payload and payload["branch"]:
        member.branch = payload["branch"].strip()
    if "year" in payload and payload["year"]:
        member.year = payload["year"].strip()
    if "student_id" in payload:
        member.student_id = payload["student_id"].strip()

    # Sync leader updates if member is leader
    if member.is_leader:
        if member.full_name: team.leader_name = member.full_name
        if member.email: team.leader_email = member.email
        if member.phone: team.leader_phone = member.phone
        if member.gender: team.leader_gender = member.gender
        if member.course: team.leader_course = member.course
        if member.branch: team.leader_branch = member.branch
        if member.year: team.leader_year = member.year

    db.commit()

    try:
        from ..d1_sync import sync_team_to_d1, sync_member_to_d1
        sync_team_to_d1(team)
        sync_member_to_d1(member)
    except Exception:
        pass

    try:
        import asyncio
        from .live import notify_live_subscribers
        asyncio.create_task(notify_live_subscribers("members"))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Member {member.full_name} details updated successfully.",
        "member": {
            "id": member.id,
            "name": member.full_name,
            "email": member.email,
            "phone": member.phone,
            "gender": member.gender,
            "course": member.course,
            "branch": member.branch,
            "year": member.year,
            "is_leader": member.is_leader
        }
    }
