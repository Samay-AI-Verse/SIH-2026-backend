import json
import os
import pathlib
from sqlalchemy.orm import Session
from .models import Admin, Setting, Problem
from .auth import get_password_hash
from .config import settings

def seed_database(db: Session):
    # 0. Migrate missing columns in payments table if needed
    try:
        from sqlalchemy import text
        db.execute(text("ALTER TABLE payments ADD COLUMN payment_mode VARCHAR DEFAULT 'ONLINE'"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        db.execute(text("ALTER TABLE payments ADD COLUMN collector_name VARCHAR"))
    except Exception:
        pass
    try:
        from sqlalchemy import text
        db.execute(text("ALTER TABLE payments ADD COLUMN receipt_no VARCHAR"))
    except Exception:
        pass
    db.commit()

    # 1. Seed Registration Settings
    existing_setting = db.query(Setting).filter(Setting.id == "registration").first()
    if not existing_setting:
        db.add(Setting(
            id="registration",
            fee=settings.REGISTRATION_FEE,
            currency=settings.CURRENCY,
            is_active=True,
            min_members=settings.REQUIRED_MEMBERS_COUNT,
            max_members=settings.REQUIRED_MEMBERS_COUNT,
            female_required=settings.FEMALE_REQUIRED
        ))
        db.commit()

    # 2. Seed Default Admin
    admin_email = settings.ADMIN_EMAIL.lower()
    existing_admin = db.query(Admin).filter(Admin.email == admin_email).first()
    if not existing_admin:
        db.add(Admin(
            email=admin_email,
            name="SIH Organizer",
            role="ADMIN",
            password_hash=get_password_hash(settings.ADMIN_PASSWORD)
        ))
        db.commit()

    # 3. Seed Open Innovation Problem Statement
    open_inno = db.query(Problem).filter(Problem.id == "OPEN_INNOVATION").first()
    if not open_inno:
        db.add(Problem(
            id="OPEN_INNOVATION",
            code="OPEN_INNO",
            title="Open Innovation - Bring Your Own Idea",
            organization="Ministry / Open Category",
            category="Software / Hardware",
            theme="Open Innovation",
            difficulty="Custom",
            description="Got an innovative idea outside the listed problem statements? Choose Open Innovation and submit your custom problem title, abstract, and architecture solution!",
            background="Encouraging student breakthroughs in AI, IoT, Web3, FinTech, Healthcare, Agriculture, and Sustainability.",
            expected_solution="A working software or hardware prototype solving a high-impact real-world challenge.",
            technical_requirements=json.dumps(["Open Tech Stack", "Modern Frameworks", "Scalable Cloud Architecture"]),
            technologies=json.dumps(["Python", "React", "Node", "FastAPI", "AI/ML", "Cloudflare", "Docker"]),
            constraint_items=json.dumps(["Original work", "Working prototype required for grand finale"]),
            evaluation_criteria=json.dumps(["Novelty & Innovation", "Technical Complexity", "Feasibility & Market Impact"]),
            selected_count=0,
            max_selections=9999, # Open Innovation has unlimited team capacity!
            is_open_innovation=True,
            status="AVAILABLE",
            sort_order=0
        ))
        db.commit()

    # 4. Seed Standard SIH Problem Statements
    count = db.query(Problem).count()
    if count <= 1: # Only Open Innovation or empty
        base_dir = pathlib.Path(__file__).resolve().parent.parent.parent
        json_path = base_dir / "SIH-Frontend" / "src" / "data" / "problem-statements.json"
        if not json_path.exists():
            json_path = base_dir / "src" / "data" / "problem-statements.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                problems_data = json.load(f)
                for item in problems_data:
                    prob = Problem(
                        id=item["id"],
                        code=item.get("code", item["id"]),
                        title=item["title"],
                        organization=item.get("organization", ""),
                        category=item.get("category", "Software"),
                        theme=item.get("theme", ""),
                        difficulty=item.get("difficulty", "Medium"),
                        description=item.get("description", ""),
                        background=item.get("background", ""),
                        expected_solution=item.get("expectedSolution", ""),
                        technical_requirements=json.dumps(item.get("technicalRequirements", [])),
                        technologies=json.dumps(item.get("technologies", [])),
                        constraint_items=json.dumps(item.get("constraints", [])),
                        evaluation_criteria=json.dumps(item.get("evaluationCriteria", [])),
                        selected_count=0,
                        max_selections=2, # Max 2 teams per problem statement!
                        is_open_innovation=False,
                        status="AVAILABLE",
                        sort_order=item.get("sortOrder", 100)
                    )
                    db.add(prob)
            db.commit()
