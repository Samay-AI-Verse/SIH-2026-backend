from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from ..database import get_db
from ..models import Team, Member, Payment, Problem, Admin, Setting, AdminLoginLog
from ..schemas import (
    PaymentVerifyRequest,
    ExpenseCreateRequest,
    TeamCancelRequest,
    TeamNameUpdateRequest,
    AdminCreateRequest,
    AdminProfileUpdateRequest,
    AdminPasswordChangeRequest,
    ForceLogoutResponse,
)
from ..auth import get_current_admin, get_password_hash, verify_password, create_access_token
from ..r2_storage import generate_presigned_download_url


router = APIRouter(prefix="/api/admin", tags=["Admin Operations"])

@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    teams = db.query(Team).all()
    total_teams = len(teams)
    total_members = db.query(Member).join(Team, Member.team_id == Team.id).count()
    paid_teams = sum(1 for t in teams if t.payment_status == "SUCCESS")
    pending_teams = sum(1 for t in teams if t.payment_status in ["PENDING", "PROCESSING"])
    failed_teams = sum(1 for t in teams if t.payment_status in ["FAILED", "CANCELLED", "REFUNDED"])
    selected_problems_count = sum(1 for t in teams if t.selected_problem_id is not None)
    open_innovation_teams = sum(1 for t in teams if t.is_open_innovation)
    
    # Total revenue from SUCCESS payments
    total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "SUCCESS").scalar() or 0.0

    from ..models import Expense
    total_expenses = db.query(func.sum(Expense.amount)).scalar() or 0.0
    net_balance = total_revenue - total_expenses

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
        "total_candidates": total_members,
        "paid_teams": paid_teams,
        "pending_teams": pending_teams,
        "failed_teams": failed_teams,
        "selected_problems_count": selected_problems_count,
        "open_innovation_teams": open_innovation_teams,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
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
            "selected_problem_code": t.selected_problem_id,
            "selectedProblemCode": t.selected_problem_id,
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
        team = db.query(Team).filter(Team.registration_id == req.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    payment = db.query(Payment).filter((Payment.team_id == team.id) | (Payment.team_id == team.registration_id)).first()
    if not payment:
        import uuid
        payment = Payment(
            id=str(uuid.uuid4()),
            team_id=team.id,
            registration_id=team.registration_id,
            team_name=team.team_name,
            order_id=f"ORD-{team.registration_id}",
            amount=300.0,
            status=req.status.upper()
        )
        db.add(payment)

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

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("all"))
    except Exception:
        pass

    return {
        "success": True,
        "team_id": team.id,
        "payment_status": team.payment_status,
        "registration_status": team.registration_status
    }

@router.get("/payments")
def list_all_payments(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    payments = db.query(Payment).order_by(Payment.created_at.desc()).all()
    results = []
    teams_dict = {t.id: t for t in db.query(Team).all()}

    for p in payments:
        team = teams_dict.get(p.team_id)
        proof_url = None
        if p.proof_key:
            proof_url = generate_presigned_download_url(p.proof_key)
        elif p.proof_url:
            proof_url = p.proof_url
        elif team:
            payment_last = db.query(Payment).filter(Payment.team_id == team.id).order_by(Payment.created_at.desc()).first()
            if payment_last and payment_last.proof_url:
                proof_url = payment_last.proof_url

        results.append({
            "id": p.id,
            "team_id": p.team_id,
            "registration_id": p.registration_id or (team.registration_id if team else ""),
            "team_name": p.team_name or (team.team_name if team else ""),
            "order_id": p.order_id,
            "transaction_id": p.transaction_id,
            "payment_mode": getattr(p, "payment_mode", "ONLINE") or "ONLINE",
            "collector_name": getattr(p, "collector_name", None),
            "receipt_no": getattr(p, "receipt_no", None),
            "amount": p.amount or 300.0,
            "currency": p.currency or "INR",
            "status": p.status or (team.payment_status if team else "PENDING"),
            "proof_url": proof_url,
            "admin_notes": p.admin_notes or "",
            "created_at": p.created_at
        })
    return results

@router.post("/payments/{payment_id}")
def update_payment_status(
    payment_id: str,
    req: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
    
    status_upper = (req.get("status") or "SUCCESS").upper()
    payment.status = status_upper
    
    team = db.query(Team).filter(Team.id == payment.team_id).first()
    if team:
        if status_upper == "SUCCESS":
            team.payment_status = "SUCCESS"
            team.registration_status = "CONFIRMED"
        elif status_upper == "FAILED":
            team.payment_status = "FAILED"
            team.registration_status = "PAYMENT_FAILED"
        else:
            team.payment_status = status_upper

    db.commit()

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("all"))
    except Exception:
        pass

    return {"success": True, "status": status_upper}

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

@router.post("/teams/{team_id}/cancel")
def cancel_team(
    team_id: str,
    req: Optional[TeamCancelRequest] = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        team = db.query(Team).filter(Team.registration_id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    refund = req.refund if req else False
    admin_notes = (req.admin_notes or "") if req else ""

    # Free up problem statement quota if selected
    if team.selected_problem_id:
        prob = db.query(Problem).filter(Problem.id == team.selected_problem_id).first()
        if prob:
            if prob.selected_count > 0:
                prob.selected_count -= 1
            if prob.id != "OPEN_INNOVATION" and prob.selected_count < prob.max_selections:
                prob.status = "AVAILABLE"

    if refund:
        team.registration_status = "CANCELLED_REFUNDED"
        team.payment_status = "REFUNDED"
    else:
        team.registration_status = "CANCELLED_NO_REFUND"
        team.payment_status = "CANCELLED"

    payment = db.query(Payment).filter(Payment.team_id == team.id).first()
    if payment:
        if refund:
            payment.status = "REFUNDED"
            from ..models import Expense
            expense = Expense(
                title=f"Registration Fee Refund — {team.team_name} ({team.registration_id})",
                category="Registration Refund",
                amount=payment.amount or 300.0,
                paid_to=team.leader_name,
                notes=f"Admin issued refund on cancellation. {admin_notes}".strip()
            )
            db.add(expense)
        else:
            payment.status = "CANCELLED"
        if admin_notes:
            payment.admin_notes = admin_notes

    db.commit()
    try:
        import asyncio
        from .live import notify_live_subscribers
        asyncio.create_task(notify_live_subscribers("teams"))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Team {team.team_name} successfully cancelled ({'Refund recorded' if refund else 'No refund'}).",
        "registration_status": team.registration_status,
        "payment_status": team.payment_status
    }

@router.put("/teams/{team_id}/name")
def update_team_name(
    team_id: str,
    req: TeamNameUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    new_name = req.team_name.strip()
    if len(new_name) < 3:
        raise HTTPException(status_code=400, detail="Team name must be at least 3 characters long")
        
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check duplicate team name (excluding current team)
    duplicate = db.query(Team).filter(
        func.lower(Team.team_name) == new_name.lower(),
        Team.id != team.id
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"Team name '{new_name}' is already taken by team {duplicate.registration_id}."
        )

    old_name = team.team_name
    team.team_name = new_name

    # Update associated Payment records
    payments = db.query(Payment).filter((Payment.team_id == team.id) | (Payment.registration_id == team.registration_id)).all()
    for p in payments:
        p.team_name = new_name

    db.commit()
    db.refresh(team)

    # Sync to Cloudflare D1
    try:
        from ..d1_sync import sync_team_to_d1
        sync_team_to_d1(team)
    except Exception:
        pass

    # Notify live subscribers
    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("all"))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Team name updated from '{old_name}' to '{new_name}'",
        "team_name": new_name
    }


@router.delete("/teams/{team_id}")
async def delete_team_permanently(
    team_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    team_name = team.team_name
    real_id = team.id
    reg_id = team.registration_id

    # Free up problem selection quota if applicable
    if team.selected_problem_id:
        prob = db.query(Problem).filter(Problem.id == team.selected_problem_id).first()
        if prob:
            if prob.selected_count > 0:
                prob.selected_count -= 1
            if prob.id != "OPEN_INNOVATION" and prob.selected_count < prob.max_selections:
                prob.status = "AVAILABLE"
            try:
                from ..d1_sync import sync_problem_to_d1
                sync_problem_to_d1(prob)
            except Exception:
                pass

    # Delete members by team.id or team.registration_id
    db.query(Member).filter((Member.team_id == real_id) | (Member.team_id == reg_id)).delete(synchronize_session=False)

    # Delete payment records by team.id or team.registration_id
    db.query(Payment).filter((Payment.team_id == real_id) | (Payment.registration_id == reg_id)).delete(synchronize_session=False)

    # Delete team row
    db.delete(team)
    db.commit()

    # Sync deletion to Cloudflare D1 Cloud
    try:
        from ..d1_sync import delete_team_from_d1
        delete_team_from_d1(real_id)
        if reg_id:
            delete_team_from_d1(reg_id)
    except Exception:
        pass

    # Trigger live SSE update so UI updates immediately everywhere without page refresh
    try:
        from .live import notify_live_subscribers
        await notify_live_subscribers("all")
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Team '{team_name}' and all associated members, payments, and problem quotas were permanently reset and deleted from database."
    }

@router.get("/analytics/daily")
def get_daily_registration_analytics(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    teams = db.query(Team).all()
    
    # Group teams and student members by registration date (YYYY-MM-DD)
    date_map = {}
    
    for t in teams:
        raw_date = t.registered_at or t.created_at if hasattr(t, "created_at") else None
        if raw_date:
            try:
                date_str = raw_date[:10]
            except Exception:
                date_str = "Unknown"
        else:
            date_str = "Unknown"
            
        if date_str not in date_map:
            date_map[date_str] = {
                "date": date_str,
                "teams_count": 0,
                "students_count": 0,
                "confirmed_teams": 0,
                "pending_teams": 0
            }
            
        date_map[date_str]["teams_count"] += 1
        m_count = len(t.members) if t.members else 6
        date_map[date_str]["students_count"] += m_count
        
        is_confirmed = t.registration_status == "CONFIRMED" or t.payment_status == "SUCCESS"
        if is_confirmed:
            date_map[date_str]["confirmed_teams"] += 1
        else:
            date_map[date_str]["pending_teams"] += 1

    sorted_dates = sorted(date_map.values(), key=lambda x: x["date"], reverse=True)
    
    total_teams = len(teams)
    total_students = sum(d["students_count"] for d in sorted_dates)
    
    return {
        "total_teams": total_teams,
        "total_students": total_students,
        "daily_breakdown": sorted_dates
    }

@router.get("/users")
def list_admin_users(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    admins = db.query(Admin).order_by(Admin.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "email": a.email,
            "name": a.name,
            "role": a.role,
            "created_by": getattr(a, "created_by", "MASTER_ADMIN") or "MASTER_ADMIN",
            "google_email": getattr(a, "google_email", None),
            "last_login_at": getattr(a, "last_login_at", None),
            "created_at": a.created_at
        }
        for a in admins
    ]

@router.post("/users")
def create_admin_user(
    req: AdminCreateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    # Only SUPER_ADMIN can grant Admin privileges
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only Chief Super Admin can grant Admin privileges to students/organizers."
        )

    clean_email = req.email.lower().strip()
    existing = db.query(Admin).filter(Admin.email == clean_email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Admin account with email '{clean_email}' already exists.")

    new_role = (req.role or "ADMIN").upper().strip()
    if new_role not in ["SUPER_ADMIN", "ADMIN"]:
        new_role = "ADMIN"

    creator_tag = f"{current_admin.name} ({current_admin.email})"
    new_admin = Admin(
        email=clean_email,
        name=req.name.strip(),
        role=new_role,
        created_by=creator_tag,
        google_email=req.google_email.lower().strip() if req.google_email else None,
        password_hash=get_password_hash(req.password)
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "success": True,
        "message": f"Successfully granted Admin role to {new_admin.name} ({new_admin.email}).",
        "admin": {
            "id": new_admin.id,
            "email": new_admin.email,
            "name": new_admin.name,
            "role": new_admin.role,
            "created_by": new_admin.created_by,
            "google_email": new_admin.google_email,
            "created_at": new_admin.created_at
        }
    }

@router.delete("/users/{admin_id}")
def revoke_admin_user(
    admin_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only Chief Super Admin can revoke Admin access."
        )

    target_admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not target_admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    if target_admin.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own Super Admin account.")

    admin_name = target_admin.name
    admin_email = target_admin.email
    db.delete(target_admin)
    db.commit()

    return {
        "success": True,
        "message": f"Successfully revoked Admin access for {admin_name} ({admin_email})."
    }

@router.get("/logs/login")
def get_admin_login_logs(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    logs = db.query(AdminLoginLog).order_by(AdminLoginLog.timestamp.desc()).limit(200).all()
    return [
        {
            "id": l.id,
            "admin_id": l.admin_id,
            "email": l.email,
            "name": l.name,
            "role": l.role,
            "google_email": getattr(l, "google_email", None),
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "status": l.status,
            "timestamp": l.timestamp
        }
        for l in logs
    ]

@router.post("/profile/update")
def update_admin_profile(
    req: AdminProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    # Verify current password if password is to be changed or email updated
    if req.current_password or req.new_password:
        if not req.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to change password.")
        if not verify_password(req.current_password, current_admin.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if req.new_password:
            if len(req.new_password) < 6:
                raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
            current_admin.password_hash = get_password_hash(req.new_password)
            # Invalidate all prior sessions when password changes
            current_admin.token_version = (getattr(current_admin, "token_version", 1) or 1) + 1

    if req.name and req.name.strip():
        current_admin.name = req.name.strip()

    if req.email and req.email.strip().lower() != current_admin.email.lower():
        new_email = req.email.strip().lower()
        conflict = db.query(Admin).filter(Admin.email == new_email).first()
        if conflict:
            raise HTTPException(status_code=400, detail=f"Email '{new_email}' is already taken by another admin.")
        current_admin.email = new_email
        # Increment token version to revoke previous tokens
        current_admin.token_version = (getattr(current_admin, "token_version", 1) or 1) + 1

    db.commit()
    db.refresh(current_admin)

    # Generate a fresh access token for current admin with updated info
    new_token = create_access_token(
        data={"sub": current_admin.email, "role": current_admin.role, "ver": current_admin.token_version}
    )

    return {
        "success": True,
        "message": "Admin profile updated successfully.",
        "access_token": new_token,
        "token_type": "bearer",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "name": current_admin.name,
            "role": current_admin.role
        }
    }

@router.post("/change-password")
def change_admin_password(
    req: AdminPasswordChangeRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    if not verify_password(req.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    
    current_admin.password_hash = get_password_hash(req.new_password)
    current_admin.token_version = (getattr(current_admin, "token_version", 1) or 1) + 1
    db.commit()

    new_token = create_access_token(
        data={"sub": current_admin.email, "role": current_admin.role, "ver": current_admin.token_version}
    )

    return {
        "success": True,
        "message": "Password changed successfully. All other active devices have been logged out.",
        "access_token": new_token,
        "token_type": "bearer"
    }

@router.post("/force-logout-all", response_model=ForceLogoutResponse)
async def force_logout_all_devices(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    # Invalidate tokens for all admins by bumping token_version
    admins = db.query(Admin).all()
    for adm in admins:
        adm.token_version = (getattr(adm, "token_version", 1) or 1) + 1
    db.commit()

    # Broadcast FORCE_LOGOUT to all connected SSE clients
    try:
        from .live import notify_live_subscribers
        await notify_live_subscribers("FORCE_LOGOUT")
    except Exception:
        pass

    from datetime import datetime, timezone
    return {
        "success": True,
        "message": "All sessions across all devices have been revoked and logged out.",
        "logged_out_at": datetime.now(timezone.utc).isoformat()
    }




