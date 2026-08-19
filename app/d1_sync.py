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
