from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Team, Member, Payment, Problem
from ..schemas import TeamLookupRequest
from ..r2_storage import generate_presigned_download_url

router = APIRouter(prefix="/api/dashboard", tags=["User Team Dashboard"])

@router.post("/lookup")
def lookup_team_status(req: TeamLookupRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    
    query = db.query(Team)
    
    # Search by leader email first
    teams = query.filter(func.lower(Team.leader_email) == email_clean).order_by(Team.registered_at.desc()).all()
    
    team = None
    if teams:
        if len(teams) == 1:
            team = teams[0]
        else:
            # If multiple teams under same email, refine by reg_id or team_name if provided
            if req.registration_id and req.registration_id.strip():
                reg_id_clean = req.registration_id.strip().upper()
                for t in teams:
                    if t.registration_id and t.registration_id.upper() == reg_id_clean:
                        team = t
                        break
            if not team and req.team_name and req.team_name.strip():
                t_name_clean = req.team_name.strip().lower()
                for t in teams:
                    if t.team_name and t.team_name.strip().lower() == t_name_clean:
                        team = t
                        break
            if not team:
                team = teams[0]
    else:
        # Fallback check if user is a registered team member
        member = db.query(Member).filter(func.lower(Member.email) == email_clean).first()
        if member:
            team = db.query(Team).filter(Team.id == member.team_id).first()
        
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this Leader Email. Please double check your email address."
        )

    # Get latest payment info & proof URL
    payment = db.query(Payment).filter(Payment.team_id == team.id).order_by(Payment.created_at.desc()).first()
    proof_url = None
    if payment and payment.proof_key:
        proof_url = generate_presigned_download_url(payment.proof_key)
    elif payment and payment.proof_url:
        proof_url = payment.proof_url

    # Get problem info
    problem_details = None
    if team.selected_problem_id:
        prob = db.query(Problem).filter(Problem.id == team.selected_problem_id).first()
        if prob:
            problem_details = {
                "id": prob.id,
                "code": prob.code,
                "title": prob.title,
                "category": prob.category,
                "theme": prob.theme,
                "difficulty": prob.difficulty
            }

    members_data = [
        {
            "id": m.id,
            "is_leader": m.is_leader,
            "name": m.full_name,
            "email": m.email,
            "phone": m.phone,
            "gender": m.gender,
            "college": m.college,
            "course": m.course,
            "branch": m.branch,
            "year": m.year,
            "student_id": m.student_id
        }
        for m in team.members
    ]

    return {
        "success": True,
        "team": {
            "id": team.id,
            "registration_id": team.registration_id,
            "team_name": team.team_name,
            "college": team.college,
            "university": team.university,
            "city": team.city,
            "state": team.state,
            "leader_name": team.leader_name,
            "leader_email": team.leader_email,
            "leader_phone": team.leader_phone,
            "leader_gender": team.leader_gender,
            "leader_branch": team.leader_branch,
            "leader_year": team.leader_year,
            "registration_status": team.registration_status,
            "payment_status": team.payment_status,
            "selected_problem_id": team.selected_problem_id,
            "selected_problem_title": team.selected_problem_title,
            "is_open_innovation": team.is_open_innovation,
            "open_innovation_title": team.open_innovation_title,
            "open_innovation_description": team.open_innovation_description,
            "registered_at": team.registered_at,
            "problem": problem_details
        },
        "members": members_data,
        "payment": {
            "order_id": payment.order_id if payment else None,
            "transaction_id": payment.transaction_id if payment else None,
            "payment_mode": getattr(payment, "payment_mode", "ONLINE") or "ONLINE" if payment else "ONLINE",
            "collector_name": getattr(payment, "collector_name", None) if payment else None,
            "receipt_no": getattr(payment, "receipt_no", None) if payment else None,
            "amount": payment.amount if payment else 300.0,
            "currency": payment.currency if payment else "INR",
            "status": payment.status if payment else "PENDING",
            "proof_url": proof_url,
            "submitted_at": payment.updated_at if payment else None
        }
    }
