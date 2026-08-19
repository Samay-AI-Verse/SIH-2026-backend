from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from ..database import get_db
from ..models import Team, Member, Payment, Problem, Admin, Setting
from ..schemas import PaymentVerifyRequest, ExpenseCreateRequest
from ..auth import get_current_admin
from ..r2_storage import generate_presigned_download_url

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"])

@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    teams = db.query(Team).all()
    total_teams = len(teams)
    total_members = db.query(Member).count()
    paid_teams = sum(1 for t in teams if t.payment_status == "SUCCESS")
    pending_teams = sum(1 for t in teams if t.payment_status in ["PENDING", "PROCESSING"])
    selected_problems_count = sum(1 for t in teams if t.selected_problem_id is not None)
    open_innovation_teams = sum(1 for t in teams if t.is_open_innovation)
    
    # Total revenue
    total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "SUCCESS").scalar() or 0.0

    # Stream / Degree Breakdown
    stream_counts = {
        "B.Tech": 0,
        "Diploma": 0,
        "B.Voc": 0,
        "BCA": 0,
        "MCA": 0,
        "Other": 0
    }

    # Year Breakdown & Composition (Same year vs Mixed years)
    year_counts = {
        "1st Year": 0,
        "2nd Year": 0,
        "3rd Year": 0,
        "4th Year": 0,
        "Mixed Years": 0
    }

    for t in teams:
        st = (t.leader_course or "").strip()
        if st in stream_counts:
            stream_counts[st] += 1
        elif st:
            stream_counts["Other"] += 1

        # Check year composition of team
        member_years = set()
        for m in t.members:
            if m.year:
                member_years.add(m.year.strip())
        
        if len(member_years) == 1:
            y = list(member_years)[0]
            if y in year_counts:
                year_counts[y] += 1
        elif len(member_years) > 1:
            year_counts["Mixed Years"] += 1
        elif t.leader_year:
            ly = t.leader_year.strip()
            if ly in year_counts:
                year_counts[ly] += 1

    return {
        "total_teams": total_teams,
        "total_members": total_members,
        "paid_teams": paid_teams,
        "pending_teams": pending_teams,
        "selected_problems_count": selected_problems_count,
        "open_innovation_teams": open_innovation_teams,
        "total_revenue": total_revenue,
        "stream_counts": stream_counts,
        "year_counts": year_counts
    }

@router.get("/teams")
def list_all_teams(
    status_filter: Optional[str] = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    query = db.query(Team)
    
    if status_filter:
        query = query.filter(Team.registration_status == status_filter)
    if payment_filter:
        query = query.filter(Team.payment_status == payment_filter)
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(Team.team_name).like(term) |
            func.lower(Team.registration_id).like(term) |
            func.lower(Team.leader_name).like(term) |
            func.lower(Team.leader_email).like(term) |
            func.lower(Team.college).like(term) |
            func.lower(Team.leader_course).like(term) |
            func.lower(Team.leader_branch).like(term)
        )

    teams = query.order_by(Team.registered_at.desc()).all()
    results = []
    
    for t in teams:
        payment = db.query(Payment).filter(Payment.team_id == t.id).order_by(Payment.created_at.desc()).first()
        proof_url = None
        if payment and payment.proof_key:
            proof_url = generate_presigned_download_url(payment.proof_key)
        elif payment and payment.proof_url:
            proof_url = payment.proof_url

        members_list = [
            {
                "id": m.id,
                "is_leader": m.is_leader,
                "name": m.full_name,
                "email": m.email,
                "phone": m.phone,
                "gender": m.gender,
                "college": m.college,
                "course": m.course or t.leader_course,
                "stream": m.course or t.leader_course,
                "branch": m.branch or t.leader_branch,
                "year": m.year or t.leader_year,
                "student_id": m.student_id
            }
            for m in t.members
        ]

        # Determine year composition
        unique_years = {m["year"] for m in members_list if m["year"]}
        year_composition = "Same Year" if len(unique_years) <= 1 else "Mixed Years"

        results.append({
            "id": t.id,
            "registration_id": t.registration_id,
            "registrationId": t.registration_id,
            "team_name": t.team_name,
            "teamName": t.team_name,
            "college": t.college,
            "university": t.university,
            "city": t.city,
            "state": t.state,
            "leader_name": t.leader_name,
            "leaderName": t.leader_name,
            "leader_email": t.leader_email,
            "leaderEmail": t.leader_email,
            "leader_phone": t.leader_phone,
            "leaderPhone": t.leader_phone,
            "leader_gender": t.leader_gender,
            "leader_course": t.leader_course,
            "leaderCourse": t.leader_course,
            "stream": t.leader_course,
            "course": t.leader_course,
            "leader_branch": t.leader_branch,
            "leaderBranch": t.leader_branch,
            "branch": t.leader_branch,
            "leader_year": t.leader_year,
            "leaderYear": t.leader_year,
            "year": t.leader_year,
            "year_composition": year_composition,
            "yearComposition": year_composition,
            "registration_status": t.registration_status,
            "registrationStatus": t.registration_status,
            "payment_status": t.payment_status,
            "paymentStatus": t.payment_status,
            "selected_problem_id": t.selected_problem_id,
            "selectedProblemId": t.selected_problem_id,
            "selected_problem_title": t.selected_problem_title,
            "selectedProblemTitle": t.selected_problem_title,
            "is_open_innovation": t.is_open_innovation,
            "open_innovation_title": t.open_innovation_title,
            "open_innovation_description": t.open_innovation_description,
            "registered_at": t.registered_at,
            "members": members_list,
            "payment": {
                "order_id": payment.order_id if payment else None,
                "utr": payment.transaction_id if payment else None,
                "transaction_id": payment.transaction_id if payment else None,
                "payment_mode": getattr(payment, "payment_mode", "ONLINE") or "ONLINE" if payment else "ONLINE",
                "collector_name": getattr(payment, "collector_name", None) if payment else None,
                "receipt_no": getattr(payment, "receipt_no", None) if payment else None,
                "amount": payment.amount if payment else 300.0,
                "status": payment.status if payment else t.payment_status,
                "proof_url": proof_url,
                "admin_notes": payment.admin_notes if payment else ""
            }
        })

    return results

@router.post("/payments/verify")
def verify_team_payment(
    req: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter(Team.id == req.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    payment = db.query(Payment).filter(Payment.team_id == team.id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    status_upper = req.status.upper()
    payment.status = status_upper
    if req.admin_notes:
        payment.admin_notes = req.admin_notes

    if status_upper == "SUCCESS":
        team.payment_status = "SUCCESS"
        team.registration_status = "CONFIRMED"
    elif status_upper == "FAILED":
        team.payment_status = "FAILED"
        team.registration_status = "PAYMENT_FAILED"
    else:
        team.payment_status = status_upper

    db.commit()
    return {
        "success": True,
        "team_id": team.id,
        "payment_status": team.payment_status,
        "registration_status": team.registration_status
    }

@router.get("/students")
def get_all_students(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    members = db.query(Member).all()
    results = []
    
    # Map team details for fast lookup
    teams_dict = {t.id: t for t in db.query(Team).all()}
    
    for m in members:
        team = teams_dict.get(m.team_id)
        if not team:
            continue
        results.append({
            "id": m.id,
            "fullName": m.full_name,
            "email": m.email,
            "phone": m.phone,
            "gender": m.gender,
            "college": m.college or team.college,
            "course": m.course or team.leader_course,
            "branch": m.branch or team.leader_branch,
            "year": m.year or team.leader_year,
            "studentId": m.student_id,
            "isLeader": m.is_leader,
            "role": "Leader" if m.is_leader else "Member",
            "teamId": team.id,
            "teamName": team.team_name,
            "registrationId": team.registration_id,
            "paymentStatus": team.payment_status,
            "selectedProblemTitle": team.open_innovation_title if team.is_open_innovation else team.selected_problem_title
        })
    return results

@router.get("/budget")
def get_budget_ledger(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    payments = db.query(Payment).all()
    successful_payments = [p for p in payments if p.status == "SUCCESS"]
    
    total_revenue = sum(p.amount for p in successful_payments)
    online_revenue = sum(p.amount for p in successful_payments if (p.payment_mode or "ONLINE") == "ONLINE")
    offline_revenue = sum(p.amount for p in successful_payments if (p.payment_mode or "ONLINE") == "OFFLINE_CASH")
    
    # Collector breakdown for offline cash
    collector_totals = {}
    for p in successful_payments:
        if (p.payment_mode or "ONLINE") == "OFFLINE_CASH" and p.collector_name:
            collector_totals[p.collector_name] = collector_totals.get(p.collector_name, 0.0) + p.amount
            
    from ..models import Expense
    expenses = db.query(Expense).order_by(Expense.created_at.desc()).all()
    total_expenses = sum(e.amount for e in expenses)
    net_balance = total_revenue - total_expenses

    return {
        "total_revenue": total_revenue,
        "online_revenue": online_revenue,
        "offline_revenue": offline_revenue,
        "collector_breakdown": collector_totals,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "expenses": [
            {
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "amount": e.amount,
                "paid_to": e.paid_to,
                "notes": e.notes,
                "created_at": e.created_at
            }
            for e in expenses
        ]
    }

@router.post("/expenses")
def create_expense(
    req: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    from ..models import Expense
    expense = Expense(
        title=req.title.strip(),
        category=req.category.strip() if req.category else "General",
        amount=float(req.amount),
        paid_to=req.paid_to.strip() if req.paid_to else "",
        notes=req.notes.strip() if req.notes else ""
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return {"success": True, "expense_id": expense.id, "message": "Expense entry added successfully"}

@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    from ..models import Expense
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense entry not found")
    db.delete(expense)
    db.commit()
    return {"success": True, "message": "Expense entry removed"}

@router.get("/problems/analytics")
def get_problems_analytics(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    problems = db.query(Problem).all()
    open_inno_teams = db.query(Team).filter(Team.is_open_innovation == True).all()
    
    total_problems = len(problems) - 1 if any(p.id == "OPEN_INNOVATION" for p in problems) else len(problems)
    locked_count = sum(1 for p in problems if p.id != "OPEN_INNOVATION" and p.selected_count >= p.max_selections)
    partial_count = sum(1 for p in problems if p.id != "OPEN_INNOVATION" and 0 < p.selected_count < p.max_selections)
    available_count = sum(1 for p in problems if p.id != "OPEN_INNOVATION" and p.selected_count == 0)
    
    return {
        "total_problems": total_problems,
        "locked_count": locked_count,
        "partial_count": partial_count,
        "available_count": available_count,
        "open_innovation_count": len(open_inno_teams),
        "open_innovation_projects": [
            {
                "team_id": t.id,
                "team_name": t.team_name,
                "title": t.open_innovation_title or "Untitled Open Innovation Project",
                "description": t.open_innovation_description or ""
            }
            for t in open_inno_teams
        ]
    }
