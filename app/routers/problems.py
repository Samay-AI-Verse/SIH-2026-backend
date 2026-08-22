import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Problem, Team
from ..schemas import ProblemSelectRequest

router = APIRouter(prefix="/api/problems", tags=["Problem Statements"])

def parse_json_field(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return []

@router.get("")
def list_problems(db: Session = Depends(get_db)):
    problems = db.query(Problem).order_by(Problem.sort_order.asc(), Problem.id.asc()).all()
    results = []
    for p in problems:
        results.append({
            "id": p.id,
            "code": p.code,
            "title": p.title,
            "organization": p.organization,
            "category": p.category,
            "theme": p.theme,
            "difficulty": p.difficulty,
            "description": p.description,
            "background": p.background,
            "expected_solution": p.expected_solution,
            "expectedSolution": p.expected_solution,
            "technical_requirements": parse_json_field(p.technical_requirements),
            "technicalRequirements": parse_json_field(p.technical_requirements),
            "technologies": parse_json_field(p.technologies),
            "constraint_items": parse_json_field(p.constraint_items),
            "constraints": parse_json_field(p.constraint_items),
            "evaluation_criteria": parse_json_field(p.evaluation_criteria),
            "evaluationCriteria": parse_json_field(p.evaluation_criteria),
            "selected_count": p.selected_count,
            "selectedCount": p.selected_count,
            "max_selections": p.max_selections,
            "maxSelections": p.max_selections,
            "is_open_innovation": (p.id == "OPEN_INNOVATION" or p.category == "Open Innovation"),
            "isOpenInnovation": (p.id == "OPEN_INNOVATION" or p.category == "Open Innovation"),
            "status": "LOCKED" if (p.id != "OPEN_INNOVATION" and p.selected_count >= p.max_selections) else p.status,
            "sort_order": p.sort_order,
            "sortOrder": p.sort_order
        })
    return results

@router.get("/{problem_id}")
def get_problem(problem_id: str, db: Session = Depends(get_db)):
    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem statement not found")
    return {
        "id": p.id,
        "code": p.code,
        "title": p.title,
        "organization": p.organization,
        "category": p.category,
        "theme": p.theme,
        "difficulty": p.difficulty,
        "description": p.description,
        "background": p.background,
        "expected_solution": p.expected_solution,
        "expectedSolution": p.expected_solution,
        "technical_requirements": parse_json_field(p.technical_requirements),
        "technicalRequirements": parse_json_field(p.technical_requirements),
        "technologies": parse_json_field(p.technologies),
        "constraint_items": parse_json_field(p.constraint_items),
        "constraints": parse_json_field(p.constraint_items),
        "evaluation_criteria": parse_json_field(p.evaluation_criteria),
        "evaluationCriteria": parse_json_field(p.evaluation_criteria),
        "selected_count": p.selected_count,
        "selectedCount": p.selected_count,
        "max_selections": p.max_selections,
        "maxSelections": p.max_selections,
        "is_open_innovation": (p.id == "OPEN_INNOVATION" or p.category == "Open Innovation"),
        "isOpenInnovation": (p.id == "OPEN_INNOVATION" or p.category == "Open Innovation"),
        "status": "LOCKED" if (p.id != "OPEN_INNOVATION" and p.selected_count >= p.max_selections) else p.status,
        "sort_order": p.sort_order
    }

@router.post("/select")
def select_problem(req: ProblemSelectRequest, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == req.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team registration not found")
    
    # Check if team already locked a problem
    if team.selected_problem_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your team has already locked problem statement: '{team.selected_problem_title or team.selected_problem_id}'. Selections cannot be changed once confirmed."
        )

    # 1. Open Innovation custom idea submission
    if req.problem_id == "OPEN_INNOVATION" or req.is_open_innovation:
        open_prob = db.query(Problem).filter(Problem.id == "OPEN_INNOVATION").first()
        if not open_prob:
            raise HTTPException(status_code=404, detail="Open Innovation category is not active")
        
        team.selected_problem_id = "OPEN_INNOVATION"
        team.selected_problem_title = req.open_innovation_title or "Open Innovation Project"
        team.is_open_innovation = True
        team.open_innovation_title = req.open_innovation_title or "Custom Idea"
        team.open_innovation_description = req.open_innovation_description or ""
        open_prob.selected_count += 1
        db.commit()

        return {
            "success": True,
            "message": "Open Innovation idea locked successfully!",
            "team_id": team.id,
            "problem_id": "OPEN_INNOVATION",
            "title": team.selected_problem_title
        }

    # 2. Official SIH Problem Statement (with max 5 teams quota)
    target_ps_id = req.problem_id.strip() if req.problem_id else ""
    target_ps_title = (req.problem_title or target_ps_id).strip()

    prob = db.query(Problem).filter(Problem.id == target_ps_id).with_for_update().first()
    if not prob:
        # Dynamically insert problem statement entry if selected directly from sih.gov.in portal
        prob = Problem(
            id=target_ps_id,
            code=target_ps_id,
            title=target_ps_title,
            organization="Official SIH 2026",
            category="Software / Hardware",
            theme="SIH 2026 Official",
            difficulty="Official",
            description=f"Official SIH 2026 Problem Statement ({target_ps_id}): {target_ps_title}",
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
        if prob.selected_count >= prob.max_selections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Problem statement '{target_ps_id}' has already reached its maximum quota of 5 teams. Please choose another problem statement or Open Innovation."
            )
        prob.selected_count += 1
        if prob.selected_count >= prob.max_selections:
            prob.status = "LOCKED"

    team.selected_problem_id = prob.id
    team.selected_problem_title = target_ps_title
    team.is_open_innovation = False
    db.commit()

    return {
        "success": True,
        "message": f"Successfully locked problem statement '{prob.id}': {target_ps_title}",
        "team_id": team.id,
        "problem_id": prob.id,
        "title": target_ps_title,
        "remaining_slots": max(0, prob.max_selections - prob.selected_count)
    }
