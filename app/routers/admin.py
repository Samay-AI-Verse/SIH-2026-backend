from fastapi import Body
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
import json
from ..database import get_db
from ..models import Team, Member, Payment, Problem, Admin, Setting, AdminLoginLog, DeletedTeamArchive, utc_now
from ..schemas import (
    PaymentVerifyRequest,
    ExpenseCreateRequest,
    TeamCancelRequest,
    TeamNameUpdateRequest,
    AdminCreateRequest,
    AdminProfileUpdateRequest,
    AdminPasswordChangeRequest,
    ForceLogoutResponse,
    TeamRegisterRequest,
    TeamCheckinRequest,
    TeamBatchCheckinRequest,
    TeamProfileUpdateRequest,
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
    
    # Check-in & Goodies stats for Hackathon Day Desk
    checked_in_teams_count = sum(1 for t in teams if getattr(t, "entry_status", "PENDING") == "CHECKED_IN")
    pending_checkin_teams_count = total_teams - checked_in_teams_count
    goodies_distributed_count = sum(1 for t in teams if getattr(t, "goodies_status", "PENDING") == "COLLECTED")
    goodies_pending_count = total_teams - goodies_distributed_count
    total_goodies_kits_given = sum(getattr(t, "goodies_count", 0) or 0 for t in teams)
    present_students_count = db.query(Member).filter(Member.entry_status == "CHECKED_IN").count()

    # Accurate total revenue calculation (strictly 1 fee per confirmed team)
    setting = db.query(Setting).first()
    default_fee = float(setting.fee) if (setting and setting.fee) else 300.0

    confirmed_teams_count = db.query(Team).filter(
        (Team.payment_status == "SUCCESS") | (Team.registration_status == "CONFIRMED")
    ).count()
    
    total_revenue = float(confirmed_teams_count * default_fee)

    from ..models import Expense
    total_expenses = float(db.query(func.sum(Expense.amount)).scalar() or 0.0)
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
        "checked_in_teams_count": checked_in_teams_count,
        "pending_checkin_teams_count": pending_checkin_teams_count,
        "goodies_distributed_count": goodies_distributed_count,
        "goodies_pending_count": goodies_pending_count,
        "total_goodies_kits_given": total_goodies_kits_given,
        "present_students_count": present_students_count,
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
                "student_id": m.student_id,
                "entry_status": getattr(m, "entry_status", "PENDING") or "PENDING",
                "entryStatus": getattr(m, "entry_status", "PENDING") or "PENDING",
                "checked_in_at": getattr(m, "checked_in_at", None),
                "checkedInAt": getattr(m, "checked_in_at", None),
                "goodies_received": bool(getattr(m, "goodies_received", False)),
                "goodiesReceived": bool(getattr(m, "goodies_received", False)),
            }
            for m in t.members
        ]

        # Determine year composition
        unique_years = {m["year"] for m in members_list if m["year"]}
        year_composition = "Same Year" if len(unique_years) <= 1 else "Mixed Years"

        present_ids = []
        try:
            raw_ids = getattr(t, "present_member_ids", "[]")
            if raw_ids:
                present_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
        except Exception:
            present_ids = []

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
            "entry_status": getattr(t, "entry_status", "PENDING") or "PENDING",
            "entryStatus": getattr(t, "entry_status", "PENDING") or "PENDING",
            "checked_in_at": getattr(t, "checked_in_at", None),
            "checkedInAt": getattr(t, "checked_in_at", None),
            "checked_in_by": getattr(t, "checked_in_by", None),
            "checkedInBy": getattr(t, "checked_in_by", None),
            "desk_number": getattr(t, "desk_number", None),
            "deskNumber": getattr(t, "desk_number", None),
            "goodies_status": getattr(t, "goodies_status", "PENDING") or "PENDING",
            "goodiesStatus": getattr(t, "goodies_status", "PENDING") or "PENDING",
            "goodies_count": getattr(t, "goodies_count", 0) or 0,
            "goodiesCount": getattr(t, "goodies_count", 0) or 0,
            "goodies_collected_at": getattr(t, "goodies_collected_at", None),
            "goodiesCollectedAt": getattr(t, "goodies_collected_at", None),
            "goodies_distributed_by": getattr(t, "goodies_distributed_by", None),
            "goodiesDistributedBy": getattr(t, "goodies_distributed_by", None),
            "checkin_notes": getattr(t, "checkin_notes", "") or "",
            "checkinNotes": getattr(t, "checkin_notes", "") or "",
            "present_members_count": getattr(t, "present_members_count", 0) or 0,
            "presentMembersCount": getattr(t, "present_members_count", 0) or 0,
            "present_member_ids": present_ids,
            "presentMemberIds": present_ids,
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

@router.post("/teams/{team_id}/checkin")
def update_team_checkin(
    team_id: str,
    req: TeamCheckinRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        team = db.query(Team).filter(Team.registration_id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    admin_name = current_admin.name or "Desk Coordinator"
    now_ts = utc_now()

    # 1. Update Entry / Check-in Status
    if req.entry_status is not None:
        team.entry_status = req.entry_status.upper()
        if team.entry_status == "CHECKED_IN":
            if not team.checked_in_at:
                team.checked_in_at = now_ts
            team.checked_in_by = req.checked_in_by or admin_name
        else:
            team.checked_in_at = None
            team.checked_in_by = None

    if req.desk_number is not None:
        team.desk_number = req.desk_number.strip() if req.desk_number else None

    # 2. Update Goodies / Swag Kit Distribution Status
    if req.goodies_status is not None:
        team.goodies_status = req.goodies_status.upper()
        if team.goodies_status == "COLLECTED":
            if not team.goodies_collected_at:
                team.goodies_collected_at = now_ts
            team.goodies_distributed_by = req.goodies_distributed_by or admin_name
            team.goodies_count = req.goodies_count if req.goodies_count is not None else (len(team.members) or 6)
        else:
            team.goodies_collected_at = None
            team.goodies_distributed_by = None
            team.goodies_count = 0
    elif req.goodies_count is not None:
        team.goodies_count = req.goodies_count

    if req.checkin_notes is not None:
        team.checkin_notes = req.checkin_notes.strip()

    # 3. Update Member Attendance
    if req.present_member_ids is not None:
        present_set = set(req.present_member_ids)
        team.present_member_ids = json.dumps(list(present_set))
        team.present_members_count = len(present_set)
        
        for m in team.members:
            if m.id in present_set:
                m.entry_status = "CHECKED_IN"
                if not m.checked_in_at:
                    m.checked_in_at = now_ts
                if team.goodies_status == "COLLECTED":
                    m.goodies_received = True
            else:
                m.entry_status = "PENDING"
                m.checked_in_at = None
    elif team.entry_status == "CHECKED_IN":
        # If no specific member ids sent but team checked in, mark all members checked in
        present_ids = [m.id for m in team.members]
        team.present_member_ids = json.dumps(present_ids)
        team.present_members_count = len(present_ids)
        for m in team.members:
            m.entry_status = "CHECKED_IN"
            if not m.checked_in_at:
                m.checked_in_at = now_ts
            if team.goodies_status == "COLLECTED":
                m.goodies_received = True
    elif team.entry_status == "PENDING":
        team.present_member_ids = "[]"
        team.present_members_count = 0
        for m in team.members:
            m.entry_status = "PENDING"
            m.checked_in_at = None
            m.goodies_received = False

    team.updated_at = now_ts
    db.commit()

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("teams"))
    except Exception:
        pass

    return {
        "success": True,
        "team_id": team.id,
        "registration_id": team.registration_id,
        "entry_status": team.entry_status,
        "checked_in_at": team.checked_in_at,
        "checked_in_by": team.checked_in_by,
        "desk_number": team.desk_number,
        "goodies_status": team.goodies_status,
        "goodies_count": team.goodies_count,
        "goodies_collected_at": team.goodies_collected_at,
        "goodies_distributed_by": team.goodies_distributed_by,
        "present_members_count": team.present_members_count,
        "checkin_notes": team.checkin_notes
    }

@router.post("/teams/batch-checkin")
def batch_update_checkin(
    req: TeamBatchCheckinRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    if not req.team_ids:
        raise HTTPException(status_code=400, detail="No team IDs provided")

    teams = db.query(Team).filter(Team.id.in_(req.team_ids)).all()
    if not teams:
        teams = db.query(Team).filter(Team.registration_id.in_(req.team_ids)).all()

    admin_name = req.coordinator_name or current_admin.name or "Desk Coordinator"
    now_ts = utc_now()
    action = req.action.upper()
    updated_count = 0

    for idx, team in enumerate(teams):
        if action in ["CHECKIN", "CHECKIN_AND_GOODIES"]:
            team.entry_status = "CHECKED_IN"
            if not team.checked_in_at:
                team.checked_in_at = now_ts
            team.checked_in_by = admin_name
            if req.desk_prefix:
                team.desk_number = f"{req.desk_prefix}-{idx + 1}"
            
            # Check-in all members
            member_ids = [m.id for m in team.members]
            team.present_member_ids = json.dumps(member_ids)
            team.present_members_count = len(member_ids)
            for m in team.members:
                m.entry_status = "CHECKED_IN"
                if not m.checked_in_at:
                    m.checked_in_at = now_ts

        if action in ["GOODIES", "CHECKIN_AND_GOODIES"]:
            team.goodies_status = "COLLECTED"
            if not team.goodies_collected_at:
                team.goodies_collected_at = now_ts
            team.goodies_distributed_by = admin_name
            team.goodies_count = req.goodies_count or len(team.members) or 6
            for m in team.members:
                m.goodies_received = True

        if action == "RESET":
            team.entry_status = "PENDING"
            team.checked_in_at = None
            team.checked_in_by = None
            team.goodies_status = "PENDING"
            team.goodies_collected_at = None
            team.goodies_distributed_by = None
            team.goodies_count = 0
            team.present_member_ids = "[]"
            team.present_members_count = 0
            for m in team.members:
                m.entry_status = "PENDING"
                m.checked_in_at = None
                m.goodies_received = False

        team.updated_at = now_ts
        updated_count += 1

    db.commit()

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("teams"))
    except Exception:
        pass

    return {
        "success": True,
        "action": action,
        "updated_count": updated_count
    }

@router.post("/teams/{team_id}/seating")
def update_team_seating(
    team_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    desk_no = payload.get("desk_number") or payload.get("table_number")
    team.desk_number = desk_no.strip() if desk_no else None
    team.updated_at = utc_now()
    db.commit()

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("teams"))
    except Exception:
        pass

    return {
        "success": True,
        "team_id": team.id,
        "registration_id": team.registration_id,
        "desk_number": team.desk_number
    }

@router.post("/teams/batch-seating")
def batch_update_seating(
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    assignments = payload.get("assignments", []) # list of {"team_id": "...", "desk_number": "..."}
    updated_count = 0

    for item in assignments:
        tid = item.get("team_id")
        dno = item.get("desk_number")
        if not tid:
            continue
        team = db.query(Team).filter((Team.id == tid) | (Team.registration_id == tid)).first()
        if team:
            team.desk_number = dno.strip() if dno else None
            team.updated_at = utc_now()
            updated_count += 1

    db.commit()

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("teams"))
    except Exception:
        pass

    return {
        "success": True,
        "updated_count": updated_count
    }

@router.get("/payments")
def list_all_payments(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    payments = db.query(Payment).order_by(Payment.created_at.desc()).all()
    results = []
    teams = db.query(Team).all()
    teams_dict = {t.id: t for t in teams}
    teams_by_reg = {t.registration_id: t for t in teams if t.registration_id}

    for p in payments:
        team = teams_dict.get(p.team_id) or teams_by_reg.get(p.team_id) or teams_by_reg.get(p.registration_id)
        
        # Auto-heal status synchronization:
        # If team is already SUCCESS or CONFIRMED, the payment must be SUCCESS
        effective_status = p.status or "PENDING"
        if team and (team.payment_status == "SUCCESS" or team.registration_status == "CONFIRMED"):
            effective_status = "SUCCESS"
            if p.status != "SUCCESS":
                p.status = "SUCCESS"
                db.add(p)
        elif team and team.payment_status in ["FAILED", "CANCELLED", "REFUNDED"]:
            effective_status = team.payment_status
            if p.status != team.payment_status:
                p.status = team.payment_status
                db.add(p)

        proof_url = None
        if p.proof_key:
            proof_url = generate_presigned_download_url(p.proof_key)
        elif p.proof_url:
            proof_url = p.proof_url
        elif team:
            payment_last = db.query(Payment).filter((Payment.team_id == team.id) | (Payment.registration_id == team.registration_id)).order_by(Payment.created_at.desc()).first()
            if payment_last and payment_last.proof_url:
                proof_url = payment_last.proof_url

        results.append({
            "id": p.id,
            "team_id": team.id if team else p.team_id,
            "registration_id": p.registration_id or (team.registration_id if team else ""),
            "team_name": p.team_name or (team.team_name if team else ""),
            "order_id": p.order_id,
            "transaction_id": p.transaction_id,
            "payment_mode": getattr(p, "payment_mode", "ONLINE") or "ONLINE",
            "collector_name": getattr(p, "collector_name", None),
            "receipt_no": getattr(p, "receipt_no", None),
            "amount": p.amount or 300.0,
            "currency": p.currency or "INR",
            "status": effective_status,
            "proof_url": proof_url,
            "admin_notes": p.admin_notes or "",
            "created_at": p.created_at
        })
    db.commit()
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
    setting = db.query(Setting).first()
    default_fee = float(setting.fee) if (setting and setting.fee) else 300.0

    teams = db.query(Team).all()
    confirmed_teams = [t for t in teams if t.payment_status == "SUCCESS" or t.registration_status == "CONFIRMED"]
    
    payments = db.query(Payment).filter(Payment.status == "SUCCESS").all()
    team_payment_map = {}
    for p in payments:
        tid = p.team_id or p.id
        if tid not in team_payment_map:
            team_payment_map[tid] = p

    def normalize_collector(name: Optional[str]) -> str:
        if not name:
            return "Desk / Other"
        n = name.strip()
        nl = n.lower()
        if "mrunal" in nl or nl == "mru":
            return "Mrunal"
        if "sadik" in nl:
            return "Sadik Gonarkar"
        if "prathmesh" in nl or "prathamesh" in nl:
            return "Prathmesh"
        if "abhay" in nl:
            return "Abhay Tak"
        if "samay" in nl:
            return "Samay"
        if "jadu" in nl:
            return "Jadu"
        return n.title()

    online_count = 0
    offline_count = 0
    collector_totals = {}

    for t in confirmed_teams:
        p = team_payment_map.get(t.id) or team_payment_map.get(t.registration_id)
        mode = (p.payment_mode if p else getattr(t, "payment_mode", "ONLINE")) or "ONLINE"
        fee = float(p.amount) if (p and p.amount) else default_fee

        if mode == "OFFLINE_CASH":
            offline_count += 1
            col = normalize_collector(p.collector_name if p else getattr(t, "collector_name", None))
            collector_totals[col] = collector_totals.get(col, 0.0) + fee
        else:
            online_count += 1

    total_revenue = float(len(confirmed_teams) * default_fee)
    online_revenue = float(online_count * default_fee)
    offline_revenue = float(offline_count * default_fee)

    from ..models import Expense
    expenses = db.query(Expense).order_by(Expense.created_at.desc()).all()
    total_expenses = float(sum(e.amount for e in expenses))
    net_balance = total_revenue - total_expenses

    return {
        "total_revenue": total_revenue,
        "online_revenue": online_revenue,
        "offline_revenue": offline_revenue,
        "online_teams_count": online_count,
        "offline_teams_count": offline_count,
        "total_confirmed_teams": len(confirmed_teams),
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


@router.put("/teams/{team_id}/profile")
@router.post("/teams/{team_id}/profile")
def update_team_profile(
    team_id: str,
    req: TeamProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # 1. Update Team Registration ID (if provided and changed)
    if req.registration_id and req.registration_id.strip():
        new_reg_id = req.registration_id.strip().upper()
        if new_reg_id != team.registration_id:
            duplicate_reg = db.query(Team).filter(Team.registration_id == new_reg_id, Team.id != team.id).first()
            if duplicate_reg:
                raise HTTPException(status_code=400, detail=f"Registration ID '{new_reg_id}' is already assigned to team '{duplicate_reg.team_name}'.")
            
            old_reg_id = team.registration_id
            team.registration_id = new_reg_id
            
            # Update payments referencing old registration ID
            payments = db.query(Payment).filter(Payment.registration_id == old_reg_id).all()
            for p in payments:
                p.registration_id = new_reg_id

    # 2. Update Team Name
    if req.team_name and req.team_name.strip():
        new_name = req.team_name.strip()
        if new_name != team.team_name:
            dup = db.query(Team).filter(func.lower(Team.team_name) == new_name.lower(), Team.id != team.id).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"Team name '{new_name}' is already taken.")
            team.team_name = new_name
            payments = db.query(Payment).filter((Payment.team_id == team.id) | (Payment.registration_id == team.registration_id)).all()
            for p in payments:
                p.team_name = new_name

    # 3. Update Stream / Course, Department / Branch, Year & College
    if req.college is not None:
        team.college = req.college.strip()
    if req.leader_course is not None:
        team.leader_course = req.leader_course.strip()
    if req.leader_branch is not None:
        team.leader_branch = req.leader_branch.strip()
    if req.leader_year is not None:
        team.leader_year = req.leader_year.strip()
    if req.leader_name is not None:
        team.leader_name = req.leader_name.strip()
    if req.leader_email is not None:
        team.leader_email = req.leader_email.strip()
    if req.leader_phone is not None:
        team.leader_phone = req.leader_phone.strip()
    if req.leader_gender is not None:
        team.leader_gender = req.leader_gender.strip()
    if req.leader_student_id is not None:
        team.leader_student_id = req.leader_student_id.strip()

    # Sync leader member in team.members
    for m in team.members:
        if m.is_leader or m.email == team.leader_email or m.name == team.leader_name:
            if req.leader_name:
                m.name = req.leader_name.strip()
            if req.leader_email:
                m.email = req.leader_email.strip()
            if req.leader_phone:
                m.phone = req.leader_phone.strip()
            if req.leader_gender:
                m.gender = req.leader_gender.strip()
            if req.leader_course:
                m.course = req.leader_course.strip()
            if req.leader_branch:
                m.branch = req.leader_branch.strip()
            if req.leader_year:
                m.year = req.leader_year.strip()
            if req.leader_student_id:
                m.student_id = req.leader_student_id.strip()
            break

    team.updated_at = utc_now()
    db.commit()
    db.refresh(team)

    try:
        from ..d1_sync import sync_team_to_d1
        sync_team_to_d1(team)
    except Exception:
        pass

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("all"))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Team profile for '{team.team_name}' ({team.registration_id}) successfully updated.",
        "team": {
            "id": team.id,
            "registration_id": team.registration_id,
            "team_name": team.team_name,
            "college": team.college,
            "leader_course": team.leader_course,
            "leader_branch": team.leader_branch,
            "leader_year": team.leader_year,
            "leader_name": team.leader_name,
            "leader_email": team.leader_email,
            "leader_phone": team.leader_phone,
            "leader_gender": team.leader_gender,
            "leader_student_id": team.leader_student_id
        }
    }


@router.delete("/teams/{team_id}")
async def delete_team_permanently(
    team_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only Chief Super Admin can permanently delete teams from the database. Sub-admins can cancel registrations."
        )
    import json
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    team_name = team.team_name
    real_id = team.id
    reg_id = team.registration_id

    # 1. Fetch and serialize all associated members
    members = db.query(Member).filter((Member.team_id == real_id) | (Member.team_id == reg_id)).all()
    members_data = [
        {
            "id": m.id,
            "full_name": m.full_name,
            "email": m.email,
            "phone": m.phone,
            "is_leader": m.is_leader,
            "gender": m.gender,
            "college": m.college,
            "course": m.course,
            "branch": m.branch,
            "year": m.year,
            "student_id": m.student_id
        }
        for m in members
    ]

    # 2. Fetch and serialize payment data
    payment = db.query(Payment).filter((Payment.team_id == real_id) | (Payment.registration_id == reg_id)).first()
    payment_data = {
        "id": payment.id if payment else None,
        "amount": payment.amount if payment else 300.0,
        "payment_status": payment.status if payment else team.payment_status,
        "payment_mode": getattr(payment, "payment_mode", "ONLINE") if payment else "ONLINE",
        "utr_number": payment.utr_number if payment else None,
        "receipt_no": getattr(payment, "receipt_no", None) if payment else None,
    } if payment else {}

    # 3. Archive the deleted record in deleted_teams_archive table
    try:
        archive_entry = DeletedTeamArchive(
            team_id=real_id,
            registration_id=reg_id,
            team_name=team.team_name,
            college=team.college or "",
            university=team.university or "",
            city=team.city or "",
            state=team.state or "",
            leader_name=team.leader_name or "",
            leader_email=team.leader_email or "",
            leader_phone=team.leader_phone or "",
            leader_gender=team.leader_gender or "",
            leader_course=team.leader_course or "",
            leader_branch=team.leader_branch or "",
            leader_year=team.leader_year or "",
            selected_problem_id=team.selected_problem_id,
            selected_problem_title=team.selected_problem_title,
            members_data=json.dumps(members_data),
            payment_data=json.dumps(payment_data),
            deleted_by_admin=current_admin.name or "Admin",
            deleted_by_email=current_admin.email,
            reason="Admin Deleted & Archived"
        )
        db.add(archive_entry)
        db.commit()
    except Exception as e:
        print("Archive notice:", e)

    # 4. Free up problem selection quota if applicable
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

    # 5. Delete members and payments
    db.query(Member).filter((Member.team_id == real_id) | (Member.team_id == reg_id)).delete(synchronize_session=False)
    db.query(Payment).filter((Payment.team_id == real_id) | (Payment.registration_id == reg_id)).delete(synchronize_session=False)

    # 6. Delete team row
    db.delete(team)
    db.commit()

    # 7. Sync deletion to Cloudflare D1 Cloud
    try:
        from ..d1_sync import delete_team_from_d1
        delete_team_from_d1(real_id)
        if reg_id:
            delete_team_from_d1(reg_id)
    except Exception:
        pass

    # 8. Trigger live SSE update
    try:
        from .live import notify_live_subscribers
        await notify_live_subscribers("all")
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Team '{team_name}' safely deleted and archived in deleted_teams_archive."
    }

@router.get("/deleted-teams")
def get_deleted_teams_archive(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    import json
    archives = db.query(DeletedTeamArchive).order_by(DeletedTeamArchive.deleted_at.desc()).all()
    results = []
    for a in archives:
        try:
            m_list = json.loads(a.members_data or "[]")
        except Exception:
            m_list = []
        try:
            p_data = json.loads(a.payment_data or "{}")
        except Exception:
            p_data = {}
        results.append({
            "id": a.id,
            "team_id": a.team_id,
            "registration_id": a.registration_id,
            "team_name": a.team_name,
            "college": a.college,
            "university": a.university,
            "leader_name": a.leader_name,
            "leader_email": a.leader_email,
            "leader_phone": a.leader_phone,
            "selected_problem_id": a.selected_problem_id,
            "selected_problem_title": a.selected_problem_title,
            "members": m_list,
            "payment": p_data,
            "deleted_by_admin": a.deleted_by_admin,
            "deleted_by_email": a.deleted_by_email,
            "deleted_at": a.deleted_at,
            "reason": a.reason
        })
    return {"deleted_teams": results, "total": len(results)}

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

    if target_admin.email.lower() in ["sih@gtmcnanded.in", "samaypowade1@gmail.com"]:
        raise HTTPException(status_code=400, detail="Cannot delete protected root Master Admin account.")

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
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only Chief Super Admin has the authority to trigger global emergency force logout."
        )

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


@router.post("/teams/{team_id}/problem-statement")
async def admin_update_team_problem_statement(
    team_id: str,
    req: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    import json
    team = db.query(Team).filter((Team.id == team_id) | (Team.registration_id == team_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    clear_selection = req.get("clear_selection", False)
    problem_id = (req.get("problem_id") or "").strip()
    problem_title = (req.get("problem_title") or "").strip()
    is_open_innovation = req.get("is_open_innovation", False) or (problem_id == "OPEN_INNOVATION")
    open_inno_title = (req.get("open_innovation_title") or "").strip()
    open_inno_desc = (req.get("open_innovation_description") or "").strip()

    # Decrement quota from old problem statement if applicable
    old_ps_id = team.selected_problem_id
    if old_ps_id and old_ps_id != "OPEN_INNOVATION":
        old_prob = db.query(Problem).filter(Problem.id == old_ps_id).first()
        if old_prob and old_prob.selected_count > 0:
            old_prob.selected_count -= 1
            if old_prob.selected_count < old_prob.max_selections:
                old_prob.status = "AVAILABLE"
            try:
                from ..d1_sync import sync_problem_to_d1
                sync_problem_to_d1(old_prob)
            except Exception:
                pass

    if clear_selection:
        team.selected_problem_id = None
        team.selected_problem_title = None
        team.is_open_innovation = False
        team.open_innovation_title = None
        team.open_innovation_description = None
        msg = "Problem statement selection cleared. Team can now re-select."
    elif is_open_innovation:
        open_prob = db.query(Problem).filter(Problem.id == "OPEN_INNOVATION").first()
        if open_prob:
            open_prob.selected_count += 1
        team.selected_problem_id = "OPEN_INNOVATION"
        team.selected_problem_title = open_inno_title or "Open Innovation Project"
        team.is_open_innovation = True
        team.open_innovation_title = open_inno_title or "Open Innovation Project"
        team.open_innovation_description = open_inno_desc
        msg = f"Assigned Open Innovation idea: '{team.selected_problem_title}'"
    else:
        if not problem_id:
            raise HTTPException(status_code=400, detail="Problem Statement ID is required")
        prob = db.query(Problem).filter(Problem.id == problem_id).first()
        if not prob:
            prob = Problem(
                id=problem_id,
                code=problem_id,
                title=problem_title or problem_id,
                organization="Official SIH 2026",
                category="Software / Hardware",
                theme="SIH 2026 Official",
                difficulty="Official",
                description=f"Official SIH 2026 Problem Statement ({problem_id}): {problem_title or problem_id}",
                background="Published on official SIH website https://sih.gov.in/sih2026PS",
                expected_solution="Working prototype solving the official problem statement.",
                technical_requirements=json.dumps(["Modern Stack"]),
                technologies=json.dumps(["Open Tech Stack"]),
                constraint_items=json.dumps(["Original implementation"]),
                evaluation_criteria=json.dumps(["Innovation", "Execution", "Feasibility"]),
                selected_count=1,
                max_selections=5,
                status="AVAILABLE",
                sort_order=100
            )
            db.add(prob)
        else:
            prob.selected_count += 1
            if prob.selected_count >= prob.max_selections:
                prob.status = "LOCKED"
        
        team.selected_problem_id = prob.id
        team.selected_problem_title = problem_title or prob.title
        team.is_open_innovation = False
        team.open_innovation_title = None
        team.open_innovation_description = None
        msg = f"Assigned Problem Statement '{prob.id}': {team.selected_problem_title}"
        try:
            from ..d1_sync import sync_problem_to_d1
            sync_problem_to_d1(prob)
        except Exception:
            pass

    db.commit()
    db.refresh(team)

    try:
        from ..d1_sync import sync_team_to_d1
        sync_team_to_d1(team)
    except Exception:
        pass

    try:
        from .live import notify_live_subscribers
        await notify_live_subscribers("all")
    except Exception:
        pass

    return {
        "success": True,
        "message": msg,
        "selected_problem_id": team.selected_problem_id,
        "selected_problem_title": team.selected_problem_title,
        "is_open_innovation": team.is_open_innovation
    }


@router.get("/settings")
def get_admin_settings(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    s = db.query(Setting).filter(Setting.id == "registration").first()
    if not s:
        s = Setting(
            id="registration",
            fee=300.0,
            currency="INR",
            is_active=True,
            min_members=6,
            max_members=6,
            female_required=True
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return {
        "fee": s.fee,
        "currency": s.currency,
        "isActive": s.is_active,
        "is_active": s.is_active,
        "minMembers": s.min_members,
        "maxMembers": s.max_members,
        "femaleRequired": s.female_required,
        "timelinePublished": bool(s.timeline_published),
        "timelineTitle": s.timeline_title or "Important Dates & Timeline",
        "timelineSubtitle": s.timeline_subtitle or "Key dates and 2-day schedule for Smart India Hackathon 2026.",
    }


@router.post("/settings")
def update_admin_settings(
    req: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    s = db.query(Setting).filter(Setting.id == "registration").first()
    if not s:
        s = Setting(id="registration")
        db.add(s)
    
    if "fee" in req:
        s.fee = float(req["fee"])
    if "currency" in req:
        s.currency = str(req["currency"])
    if "is_active" in req:
        s.is_active = bool(req["is_active"])
    elif "isActive" in req:
        s.is_active = bool(req["isActive"])
    if "min_members" in req:
        s.min_members = int(req["min_members"])
    if "max_members" in req:
        s.max_members = int(req["max_members"])
    if "female_required" in req:
        s.female_required = bool(req["female_required"])
    if "timeline_published" in req:
        s.timeline_published = bool(req["timeline_published"])
    elif "timelinePublished" in req:
        s.timeline_published = bool(req["timelinePublished"])
    if "timeline_title" in req:
        s.timeline_title = str(req["timeline_title"])
    elif "timelineTitle" in req:
        s.timeline_title = str(req["timelineTitle"])
    if "timeline_subtitle" in req:
        s.timeline_subtitle = str(req["timeline_subtitle"])
    elif "timelineSubtitle" in req:
        s.timeline_subtitle = str(req["timelineSubtitle"])

    db.commit()
    db.refresh(s)

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("settings"))
    except Exception:
        pass

    return {
        "success": True,
        "message": "Settings updated successfully.",
        "settings": {
            "fee": s.fee,
            "currency": s.currency,
            "isActive": s.is_active,
            "is_active": s.is_active,
            "minMembers": s.min_members,
            "maxMembers": s.max_members,
            "femaleRequired": s.female_required,
            "timelinePublished": bool(s.timeline_published),
            "timelineTitle": s.timeline_title,
            "timelineSubtitle": s.timeline_subtitle,
        }
    }


@router.get("/timeline")
def get_admin_timeline(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    import json
    s = db.query(Setting).filter(Setting.id == "registration").first()
    events = []
    if s and s.timeline_events:
        if isinstance(s.timeline_events, list):
            events = s.timeline_events
        elif isinstance(s.timeline_events, str):
            try:
                events = json.loads(s.timeline_events)
            except Exception:
                events = []
    return {
        "published": bool(s.timeline_published) if s else False,
        "title": s.timeline_title if s and s.timeline_title else "Important Dates & Timeline",
        "subtitle": s.timeline_subtitle if s and s.timeline_subtitle else "Key dates and 2-day schedule for Smart India Hackathon 2026.",
        "events": events
    }


@router.post("/timeline")
def update_admin_timeline(
    req: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    s = db.query(Setting).filter(Setting.id == "registration").first()
    if not s:
        s = Setting(id="registration")
        db.add(s)

    if "published" in req:
        s.timeline_published = bool(req["published"])
    if "title" in req:
        s.timeline_title = str(req["title"])
    if "subtitle" in req:
        s.timeline_subtitle = str(req["subtitle"])
    if "events" in req:
        s.timeline_events = req["events"]

    db.commit()
    db.refresh(s)

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("timeline"))
    except Exception:
        pass

    return {
        "success": True,
        "message": "Timeline updated successfully.",
        "published": bool(s.timeline_published),
        "title": s.timeline_title,
        "subtitle": s.timeline_subtitle,
        "events": s.timeline_events or []
    }


@router.post("/timeline/publish")
def toggle_timeline_publish(
    req: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    s = db.query(Setting).filter(Setting.id == "registration").first()
    if not s:
        s = Setting(id="registration")
        db.add(s)

    s.timeline_published = bool(req.get("published", True))
    db.commit()
    db.refresh(s)

    try:
        from .live import notify_live_subscribers
        import asyncio
        asyncio.create_task(notify_live_subscribers("timeline"))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Timeline is now {'PUBLIC and LIVE on website' if s.timeline_published else 'HIDDEN (Draft mode)'}.",
        "published": bool(s.timeline_published)
    }


@router.post("/teams/register")
def admin_register_team(
    req: TeamRegisterRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    from .teams import generate_registration_id
    import uuid

    team_name_clean = req.team_name.strip()
    leader_email_clean = req.leader_email.strip().lower()
    
    existing_team = db.query(Team).filter(
        func.lower(Team.team_name) == func.lower(team_name_clean)
    ).first()
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team name '{team_name_clean}' is already registered."
        )

    existing_leader = db.query(Team).filter(
        func.lower(Team.leader_email) == leader_email_clean
    ).first()
    if existing_leader:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leader email '{leader_email_clean}' is already registered with team '{existing_leader.team_name}'."
        )

    problem_title = None
    if req.selected_problem_id:
        problem = db.query(Problem).filter(Problem.id == req.selected_problem_id).first()
        if problem:
            problem_title = problem.title
            problem.selected_count += 1

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
        registration_status="CONFIRMED",
        payment_status="SUCCESS",
        selected_problem_id=req.selected_problem_id,
        selected_problem_title=problem_title,
        is_open_innovation=req.is_open_innovation or (req.selected_problem_id == "OPEN_INNOVATION"),
        open_innovation_title=req.open_innovation_title,
        open_innovation_description=req.open_innovation_description
    )
    db.add(team)
    db.flush()

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
        status="SUCCESS",
        payment_mode="ADMIN_DIRECT",
        admin_notes=f"Created directly by Admin {current_admin.name or current_admin.email}"
    )
    db.add(payment)
    db.commit()

    try:
        from ..d1_sync import sync_team_to_d1, sync_member_to_d1
        sync_team_to_d1(team)
        for m in team.members:
            sync_member_to_d1(m)
    except Exception:
        pass

    return {
        "success": True,
        "team_id": team.id,
        "registration_id": team.registration_id,
        "team_name": team.team_name,
        "message": "Team created and approved directly by Admin."
    }

# =========================================================================
# CERTIFICATE HUB & EMAIL DISPATCH ENDPOINTS
# =========================================================================

from fastapi.responses import Response
from ..certificate_service import generate_single_certificate_bytes, send_team_certificates_email

@router.get("/certificates/config")
def get_certificate_config(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    return {
        "cert_event_title": getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
        "cert_issue_date": getattr(setting, "cert_issue_date", "March 2026"),
        "cert_sign_1_name": getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
        "cert_sign_1_title": getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
        "cert_sign_2_name": getattr(setting, "cert_sign_2_name", "Principal / Director"),
        "cert_sign_2_title": getattr(setting, "cert_sign_2_title", "Head of Institution"),
        "smtp_host": getattr(setting, "smtp_host", "smtp.gmail.com") or "smtp.gmail.com",
        "smtp_port": getattr(setting, "smtp_port", 587) or 587,
        "smtp_user": getattr(setting, "smtp_user", "") or "",
        "smtp_from_name": getattr(setting, "smtp_from_name", "SIH Organizing Committee") or "SIH Organizing Committee",
        "is_smtp_configured": bool(getattr(setting, "smtp_user", "") and getattr(setting, "smtp_pass", ""))
    }

@router.post("/certificates/config")
def update_certificate_config(
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    if not setting:
        setting = Setting(id="registration")
        db.add(setting)

    if "cert_event_title" in payload:
        setting.cert_event_title = payload["cert_event_title"]
    if "cert_issue_date" in payload:
        setting.cert_issue_date = payload["cert_issue_date"]
    if "cert_sign_1_name" in payload:
        setting.cert_sign_1_name = payload["cert_sign_1_name"]
    if "cert_sign_1_title" in payload:
        setting.cert_sign_1_title = payload["cert_sign_1_title"]
    if "cert_sign_2_name" in payload:
        setting.cert_sign_2_name = payload["cert_sign_2_name"]
    if "cert_sign_2_title" in payload:
        setting.cert_sign_2_title = payload["cert_sign_2_title"]

    if "smtp_host" in payload:
        setting.smtp_host = payload["smtp_host"]
    if "smtp_port" in payload:
        setting.smtp_port = int(payload["smtp_port"])
    if "smtp_user" in payload:
        setting.smtp_user = payload["smtp_user"].strip()
    if "smtp_pass" in payload and payload["smtp_pass"].strip():
        setting.smtp_pass = payload["smtp_pass"].strip()
    if "smtp_from_name" in payload:
        setting.smtp_from_name = payload["smtp_from_name"]

    db.commit()
    return {"success": True, "message": "Certificate and SMTP settings saved successfully."}

@router.post("/certificates/test-smtp")
def test_smtp_connection(
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    host = payload.get("smtp_host") or getattr(setting, "smtp_host", "smtp.gmail.com")
    port = int(payload.get("smtp_port") or getattr(setting, "smtp_port", 587))
    user = payload.get("smtp_user") or getattr(setting, "smtp_user", "")
    pwd = payload.get("smtp_pass") or getattr(setting, "smtp_pass", "")
    target_email = payload.get("test_email") or current_admin.email or user

    if not user or not pwd:
        raise HTTPException(status_code=400, detail="SMTP Username and Password/App-Password are required.")

    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText("This is a test verification email from your SIH 2026 Hackathon Portal.")
    msg["Subject"] = "SIH 2026 - SMTP Configuration Test Successful"
    msg["From"] = user
    msg["To"] = target_email

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(user, pwd)
        server.sendmail(user, [target_email], msg.as_string())
        server.quit()
        return {"success": True, "message": f"Test email successfully delivered to {target_email}!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP Connection Failed: {str(e)}")

@router.get("/certificates/preview")
def preview_sample_certificate(
    student_name: str = "Rahul Sharma",
    team_name: str = "Code Mavericks",
    college: str = "GTMC Engineering College",
    role: str = "Leader",
    cert_type: str = "Participation",
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    pdf_bytes = generate_single_certificate_bytes(
        student_name=student_name,
        team_name=team_name,
        college_name=college,
        role=role,
        cert_type=cert_type,
        event_title=getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
        sign_1_title=getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
        sign_1_name=getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
        sign_2_title=getattr(setting, "cert_sign_2_title", "Head of Institution"),
        sign_2_name=getattr(setting, "cert_sign_2_name", "Principal / Director"),
        issue_date=getattr(setting, "cert_issue_date", "March 2026")
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Certificate_{student_name.replace(" ", "_")}.pdf"'}
    )

@router.get("/certificates/member/{member_id}")
def download_member_certificate(
    member_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    team = member.team
    setting = db.query(Setting).filter(Setting.id == "registration").first()

    role = "Leader" if member.is_leader else "Member"
    pdf_bytes = generate_single_certificate_bytes(
        student_name=member.full_name,
        team_name=team.team_name if team else "",
        college_name=member.college or (team.college if team else ""),
        role=role,
        cert_type="Participation",
        event_title=getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
        sign_1_title=getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
        sign_1_name=getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
        sign_2_title=getattr(setting, "cert_sign_2_title", "Head of Institution"),
        sign_2_name=getattr(setting, "cert_sign_2_name", "Principal / Director"),
        issue_date=getattr(setting, "cert_issue_date", "March 2026")
    )
    filename = f"Certificate_{member.full_name.replace(' ', '_')}_{team.registration_id if team else 'SIH'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/certificates/send-team/{team_id}")
def dispatch_team_certificates_email(
    team_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    setting = db.query(Setting).filter(Setting.id == "registration").first()
    smtp_host = getattr(setting, "smtp_host", "smtp.gmail.com") or "smtp.gmail.com"
    smtp_port = getattr(setting, "smtp_port", 587) or 587
    smtp_user = getattr(setting, "smtp_user", "") or ""
    smtp_pass = getattr(setting, "smtp_pass", "") or ""
    smtp_from_name = getattr(setting, "smtp_from_name", "SIH Organizing Committee") or "SIH Organizing Committee"

    if not smtp_user or not smtp_pass:
        raise HTTPException(status_code=400, detail="SMTP credentials are not configured. Please save your Gmail/SMTP details first.")

    # Generate certificates for all members
    attachments = []
    for m in team.members:
        role = "Leader" if m.is_leader else "Member"
        pdf_bytes = generate_single_certificate_bytes(
            student_name=m.full_name,
            team_name=team.team_name,
            college_name=m.college or team.college,
            role=role,
            cert_type="Participation",
            event_title=getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
            sign_1_title=getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
            sign_1_name=getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
            sign_2_title=getattr(setting, "cert_sign_2_title", "Head of Institution"),
            sign_2_name=getattr(setting, "cert_sign_2_name", "Principal / Director"),
            issue_date=getattr(setting, "cert_issue_date", "March 2026")
        )
        fn = f"Certificate_{m.full_name.replace(' ', '_')}_{team.registration_id}.pdf"
        attachments.append((fn, pdf_bytes))

    try:
        send_team_certificates_email(
            smtp_host=smtp_host,
            smtp_port=int(smtp_port),
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            from_name=smtp_from_name,
            leader_email=team.leader_email,
            leader_name=team.leader_name,
            team_name=team.team_name,
            certificate_attachments=attachments
        )
        team.cert_status = "SENT"
        team.cert_sent_at = utc_now()
        db.commit()
        return {
            "success": True,
            "team_id": team.id,
            "team_name": team.team_name,
            "leader_email": team.leader_email,
            "certificates_count": len(attachments),
            "message": f"Successfully emailed {len(attachments)} certificates to {team.leader_email}"
        }
    # pyrefly: ignore [parse-error]
    except Exception as e:
@router.post("/certificates/send-custom")
def dispatch_custom_certificate_email(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    student_name = payload.get("student_name", "").strip()
    student_email = payload.get("student_email", "").strip()
    team_name = payload.get("team_name", "").strip()
    college_name = payload.get("college_name", "").strip()
    role = payload.get("role", "Member")

    if not student_name or not student_email:
        raise HTTPException(status_code=400, detail="Student name and student email are required.")

    setting = db.query(Setting).filter(Setting.id == "registration").first()
    smtp_host = getattr(setting, "smtp_host", "smtp.gmail.com") or "smtp.gmail.com"
    smtp_port = getattr(setting, "smtp_port", 587) or 587
    smtp_user = getattr(setting, "smtp_user", "") or ""
    smtp_pass = getattr(setting, "smtp_pass", "") or ""
    smtp_from_name = getattr(setting, "smtp_from_name", "SIH Organizing Committee") or "SIH Organizing Committee"

    if not smtp_user or not smtp_pass:
        raise HTTPException(status_code=400, detail="SMTP credentials are not configured. Please save your Gmail/SMTP details in Settings first.")

    pdf_bytes = generate_single_certificate_bytes(
        student_name=student_name,
        team_name=team_name,
        college_name=college_name,
        role=role,
        cert_type="Participation",
        event_title=getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
        sign_1_title=getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
        sign_1_name=getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
        sign_2_title=getattr(setting, "cert_sign_2_title", "Head of Institution"),
        sign_2_name=getattr(setting, "cert_sign_2_name", "Principal / Director"),
        issue_date=getattr(setting, "cert_issue_date", "September 2026")
    )
    fn = f"Certificate_{student_name.replace(' ', '_')}.pdf"

    try:
        send_team_certificates_email(
            smtp_host=smtp_host,
            smtp_port=int(smtp_port),
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            from_name=smtp_from_name,
            leader_email=student_email,
            leader_name=student_name,
            team_name=team_name,
            certificate_attachments=[(fn, pdf_bytes)]
        )
        return {
            "success": True,
            "student_email": student_email,
            "message": f"Successfully emailed certificate to {student_email}!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to dispatch email: {str(e)}")







