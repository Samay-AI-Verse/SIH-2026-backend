import json
import threading
from sqlalchemy import event
from sqlalchemy.orm import Session
from .d1_client import CloudflareD1Client

d1_client = CloudflareD1Client()

def _exec_d1_async(sql, params):
    if not d1_client.is_configured():
        return
    def _worker():
        try:
            d1_client.query(sql, params)
        except Exception as e:
            print("⚠️ Cloudflare D1 Sync Warning:", e)
    threading.Thread(target=_worker, daemon=True).start()

def sync_team_to_d1(team):
    sql = """INSERT OR REPLACE INTO teams (
        id, registration_id, team_name, college, university, city, state,
        leader_name, leader_email, leader_phone, leader_gender, leader_course, leader_branch, leader_year, leader_student_id,
        registration_status, payment_status, selected_problem_id, selected_problem_title,
        is_open_innovation, open_innovation_title, open_innovation_description, registered_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
    params = [
        str(team.id),
        str(team.registration_id),
        str(team.team_name),
        str(team.college or ""),
        str(team.university or ""),
        str(team.city or ""),
        str(team.state or ""),
        str(team.leader_name or ""),
        str(team.leader_email or ""),
        str(team.leader_phone or ""),
        str(team.leader_gender or ""),
        str(team.leader_course or "B.Tech"),
        str(team.leader_branch or ""),
        str(team.leader_year or ""),
        str(team.leader_student_id or ""),
        str(team.registration_status or "CONFIRMED"),
        str(team.payment_status or "PENDING"),
        team.selected_problem_id if team.selected_problem_id else None,
        team.selected_problem_title if team.selected_problem_title else None,
        1 if team.is_open_innovation else 0,
        team.open_innovation_title if team.open_innovation_title else None,
        team.open_innovation_description if team.open_innovation_description else None,
        str(team.registered_at or ""),
        str(team.updated_at or "")
    ]
    _exec_d1_async(sql, params)

def sync_member_to_d1(member):
    sql = """INSERT OR REPLACE INTO members (
        id, team_id, full_name, email, phone, is_leader, gender, college, course, branch, year, student_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
    params = [
        str(member.id),
        str(member.team_id),
        str(member.full_name),
        str(member.email or ""),
        str(member.phone or ""),
        1 if member.is_leader else 0,
        str(member.gender or ""),
        str(member.college or ""),
        str(member.course or ""),
        str(member.branch or ""),
        str(member.year or ""),
        str(member.student_id or ""),
        str(member.created_at or "")
    ]
    _exec_d1_async(sql, params)

def sync_payment_to_d1(payment):
    sql = """INSERT OR REPLACE INTO payments (
        id, team_id, registration_id, team_name, order_id, transaction_id, proof_key, proof_url,
        payment_mode, collector_name, receipt_no, amount, currency, status, admin_notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
    params = [
        str(payment.id),
        str(payment.team_id),
        str(payment.registration_id),
        str(payment.team_name),
        str(payment.order_id),
        payment.transaction_id if payment.transaction_id else None,
        payment.proof_key if payment.proof_key else None,
        payment.proof_url if payment.proof_url else None,
        str(payment.payment_mode or "ONLINE"),
        payment.collector_name if payment.collector_name else None,
        payment.receipt_no if payment.receipt_no else None,
        float(payment.amount or 300.0),
        str(payment.currency or "INR"),
        str(payment.status or "PENDING"),
        str(payment.admin_notes or ""),
        str(payment.created_at or ""),
        str(payment.updated_at or "")
    ]
    _exec_d1_async(sql, params)

def sync_expense_to_d1(expense):
    sql = """INSERT OR REPLACE INTO expenses (
        id, title, category, amount, paid_to, notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?);"""
    params = [
        str(expense.id),
        str(expense.title),
        str(expense.category or "General"),
        float(expense.amount or 0.0),
        str(expense.paid_to or ""),
        str(expense.notes or ""),
        str(expense.created_at or "")
    ]
    _exec_d1_async(sql, params)

def sync_problem_to_d1(problem):
    sql = """INSERT OR REPLACE INTO problems (
        id, code, title, organization, category, theme, difficulty,
        description, background, expected_solution, technical_requirements,
        technologies, constraint_items, evaluation_criteria, selected_count, max_selections, status, sort_order
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
    
    tech_req = json.dumps(problem.technical_requirements) if isinstance(problem.technical_requirements, (list, dict)) else str(problem.technical_requirements or "[]")
    tech_stack = json.dumps(problem.technologies) if isinstance(problem.technologies, (list, dict)) else str(problem.technologies or "[]")
    constraints = json.dumps(problem.constraint_items) if isinstance(problem.constraint_items, (list, dict)) else str(problem.constraint_items or "[]")
    eval_crit = json.dumps(problem.evaluation_criteria) if isinstance(problem.evaluation_criteria, (list, dict)) else str(problem.evaluation_criteria or "[]")
    
    params = [
        str(problem.id),
        str(problem.code or problem.id),
        str(problem.title or ""),
        str(problem.organization or ""),
        str(problem.category or "Software"),
        str(problem.theme or ""),
        str(problem.difficulty or "Medium"),
        str(problem.description or ""),
        str(problem.background or ""),
        str(problem.expected_solution or ""),
        tech_req,
        tech_stack,
        constraints,
        eval_crit,
        int(problem.selected_count or 0),
        int(problem.max_selections or 2),
        str(problem.status or "AVAILABLE"),
        int(problem.sort_order or 0)
    ]
    _exec_d1_async(sql, params)

def delete_team_from_d1(team_id: str):
    _exec_d1_async("DELETE FROM members WHERE team_id = ? OR team_id IN (SELECT registration_id FROM teams WHERE id = ?);", [str(team_id), str(team_id)])
    _exec_d1_async("DELETE FROM payments WHERE team_id = ? OR team_id IN (SELECT registration_id FROM teams WHERE id = ?);", [str(team_id), str(team_id)])
    _exec_d1_async("DELETE FROM teams WHERE id = ? OR registration_id = ?;", [str(team_id), str(team_id)])

def delete_member_from_d1(member_id: str):
    _exec_d1_async("DELETE FROM members WHERE id = ?;", [str(member_id)])

def delete_payment_from_d1(payment_id: str):
    _exec_d1_async("DELETE FROM payments WHERE id = ?;", [str(payment_id)])

def delete_expense_from_d1(expense_id: str):
    _exec_d1_async("DELETE FROM expenses WHERE id = ?;", [str(expense_id)])

def register_d1_hooks(SessionClass):
    @event.listens_for(SessionClass, "after_flush")
    def after_flush(session, flush_context):
        for obj in session.new.union(session.dirty):
            obj_type = type(obj).__name__
            if obj_type == "Team":
                sync_team_to_d1(obj)
            elif obj_type == "Member":
                sync_member_to_d1(obj)
            elif obj_type == "Payment":
                sync_payment_to_d1(obj)
            elif obj_type == "Expense":
                sync_expense_to_d1(obj)
            elif obj_type == "Problem":
                sync_problem_to_d1(obj)

        for obj in session.deleted:
            obj_type = type(obj).__name__
            if obj_type == "Team":
                delete_team_from_d1(obj.id)
            elif obj_type == "Member":
                delete_member_from_d1(obj.id)
            elif obj_type == "Payment":
                delete_payment_from_d1(obj.id)
            elif obj_type == "Expense":
                delete_expense_from_d1(obj.id)

def sync_full_database_to_d1(db: Session):
    from .models import Team, Member, Payment, Expense, Problem
    print("🚀 Syncing current database records to Cloudflare D1 Cloud...")
    
    teams = db.query(Team).all()
    for t in teams:
        sync_team_to_d1(t)

    members = db.query(Member).all()
    for m in members:
        sync_member_to_d1(m)

    payments = db.query(Payment).all()
    for p in payments:
        sync_payment_to_d1(p)

    expenses = db.query(Expense).all()
    for e in expenses:
        sync_expense_to_d1(e)

    print("🎉 Cloudflare D1 Background Sync Triggered Successfully!")


def pull_from_d1_to_sqlite(db: Session):
    if not d1_client.is_configured():
        print("[D1 Sync] Cloudflare D1 credentials not configured. Skipping D1 startup pull.")
        return

    print("[D1 Sync] Connecting to Cloudflare D1 Cloud Database to pull data...")
    try:
        from .models import Team, Member, Payment, Expense, Problem

        def _extract_rows(d1_res):
            if isinstance(d1_res, dict):
                return d1_res.get("results", [])
            elif isinstance(d1_res, list):
                return d1_res
            return []

        from sqlalchemy import func

        # 1. Fetch Teams from D1
        teams_rows = _extract_rows(d1_client.query("SELECT * FROM teams;"))
        d1_team_ids = {str(r["id"]) for r in teams_rows}
        d1_reg_ids = {str(r.get("registration_id", "")) for r in teams_rows if r.get("registration_id")}

        # Purge teams in local SQLite that were deleted from D1
        local_teams = db.query(Team).all()
        for lt in local_teams:
            if lt.id not in d1_team_ids and lt.registration_id not in d1_reg_ids:
                db.query(Member).filter((Member.team_id == lt.id) | (Member.team_id == lt.registration_id)).delete(synchronize_session=False)
                db.query(Payment).filter((Payment.team_id == lt.id) | (Payment.registration_id == lt.registration_id)).delete(synchronize_session=False)
                db.delete(lt)
        db.commit()

        for row in teams_rows:
            team_id = str(row["id"])
            reg_id = str(row.get("registration_id", ""))
            team_name = str(row.get("team_name", ""))
            existing = db.query(Team).filter(
                (Team.id == team_id) | (Team.registration_id == reg_id) | (func.lower(Team.team_name) == team_name.lower())
            ).first()
            if not existing:
                new_team = Team(
                    id=team_id,
                    registration_id=reg_id,
                    team_name=team_name,
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
                    payment_status=str(row.get("payment_status", "PENDING")),
                    selected_problem_id=row.get("selected_problem_id"),
                    selected_problem_title=row.get("selected_problem_title"),
                    is_open_innovation=bool(row.get("is_open_innovation", 0)),
                    open_innovation_title=row.get("open_innovation_title"),
                    open_innovation_description=row.get("open_innovation_description"),
                    registered_at=str(row.get("registered_at", "")),
                    updated_at=str(row.get("updated_at", ""))
                )
                db.add(new_team)
            else:
                existing.registration_status = str(row.get("registration_status", existing.registration_status))
                existing.payment_status = str(row.get("payment_status", existing.payment_status))
                existing.selected_problem_id = row.get("selected_problem_id", existing.selected_problem_id)
                existing.selected_problem_title = row.get("selected_problem_title", existing.selected_problem_title)
            try:
                db.commit()
            except Exception:
                db.rollback()

        # 2. Fetch Members from D1
        members_rows = _extract_rows(d1_client.query("SELECT * FROM members;"))
        for row in members_rows:
            member_id = str(row["id"])
            existing_m = db.query(Member).filter(Member.id == member_id).first()
            if not existing_m:
                new_member = Member(
                    id=member_id,
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
                db.add(new_member)
            try:
                db.commit()
            except Exception:
                db.rollback()

        # 3. Fetch Payments from D1
        payments_rows = _extract_rows(d1_client.query("SELECT * FROM payments;"))
        for row in payments_rows:
            payment_id = str(row["id"])
            existing_p = db.query(Payment).filter(Payment.id == payment_id).first()
            if not existing_p:
                new_payment = Payment(
                    id=payment_id,
                    team_id=str(row.get("team_id", "")),
                    registration_id=str(row.get("registration_id", "")),
                    team_name=str(row.get("team_name", "")),
                    order_id=str(row.get("order_id", f"ORD-{payment_id[:8]}")),
                    transaction_id=row.get("transaction_id"),
                    proof_key=row.get("proof_key"),
                    proof_url=row.get("proof_url"),
                    payment_mode=str(row.get("payment_mode", "ONLINE")),
                    collector_name=row.get("collector_name"),
                    receipt_no=row.get("receipt_no"),
                    amount=float(row.get("amount", 300.0)),
                    currency=str(row.get("currency", "INR")),
                    status=str(row.get("status", "PENDING")),
                    admin_notes=str(row.get("admin_notes", "")),
                    created_at=str(row.get("created_at", "")),
                    updated_at=str(row.get("updated_at", ""))
                )
                db.add(new_payment)
            try:
                db.commit()
            except Exception:
                db.rollback()

        # 4. Fetch Expenses from D1
        expenses_rows = _extract_rows(d1_client.query("SELECT * FROM expenses;"))
        for row in expenses_rows:
            expense_id = str(row["id"])
            existing_e = db.query(Expense).filter(Expense.id == expense_id).first()
            if not existing_e:
                new_expense = Expense(
                    id=expense_id,
                    title=str(row.get("title", "")),
                    category=str(row.get("category", "General")),
                    amount=float(row.get("amount", 0.0)),
                    paid_to=str(row.get("paid_to", "")),
                    notes=str(row.get("notes", "")),
                    date=str(row.get("date", "")),
                    created_at=str(row.get("created_at", ""))
                )
                db.add(new_expense)
            try:
                db.commit()
            except Exception:
                db.rollback()

        # Purge any remaining orphan members or payments in local SQLite
        all_local_team_ids = {t.id for t in db.query(Team).all()}.union({t.registration_id for t in db.query(Team).all()})
        db.query(Member).filter(~Member.team_id.in_(all_local_team_ids)).delete(synchronize_session=False)
        db.query(Payment).filter(~Payment.team_id.in_(all_local_team_ids)).delete(synchronize_session=False)
        db.commit()

        print(f"[D1 Sync] Startup Pull Complete! Local DB has {db.query(Team).count()} teams, {db.query(Member).count()} members, {db.query(Payment).count()} payments.")
    except Exception as e:
        print("[D1 Sync] Pull Notice:", e)


