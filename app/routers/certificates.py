from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
import io

from ..database import get_db
from ..models import Team, Member, Setting
from ..certificate_service import (
    generate_single_certificate_bytes,
    generate_team_certificates_zip_bytes
)

router = APIRouter(prefix="/api/certificates", tags=["Certificates Direct Download & Lookup"])


@router.post("/lookup")
def lookup_certificates_by_email_or_id(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Public lookup for students & participants.
    Query by participant email, leader email, team registration ID, or team name.
    Returns matched participant info, all team members, and direct download links.
    """
    raw_query = (payload.get("email") or payload.get("query") or payload.get("registration_id") or "").strip()
    if not raw_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid participant email, leader email, or Registration ID."
        )

    clean_query = raw_query.lower()
    clean_reg = raw_query.upper()

    # 1. Search member first by email
    matched_member = db.query(Member).filter(func.lower(Member.email) == clean_query).first()
    team = None
    if matched_member:
        team = db.query(Team).filter(Team.id == matched_member.team_id).first()

    # 2. Search team by leader email or registration id
    if not team:
        team = db.query(Team).filter(
            or_(
                func.lower(Team.leader_email) == clean_query,
                Team.registration_id == clean_reg,
                func.lower(Team.team_name) == clean_query
            )
        ).first()

    # 3. Partial fallback search on team name or member name
    if not team:
        member_fallback = db.query(Member).filter(Member.full_name.ilike(f"%{raw_query}%")).first()
        if member_fallback:
            team = db.query(Team).filter(Team.id == member_fallback.team_id).first()
            if not matched_member:
                matched_member = member_fallback

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hackathon team or participant record found matching '{raw_query}'. Please check your email or Registration ID."
        )

    # Prepare members data with download URLs
    members_list = []
    for idx, m in enumerate(team.members):
        is_ldr = m.is_leader or (idx == 0)
        members_list.append({
            "id": m.id,
            "name": m.full_name,
            "email": m.email,
            "role": "Leader" if is_ldr else "Member",
            "is_leader": is_ldr,
            "college": m.college or team.college,
            "download_url": f"/api/certificates/member/{m.id}",
            "preview_url": f"/api/certificates/member/{m.id}?preview=true"
        })

    # If matched_member not identified yet, find leader or first member
    if not matched_member and members_list:
        matched_member_id = members_list[0]["id"]
    else:
        matched_member_id = matched_member.id if matched_member else None

    return {
        "success": True,
        "team": {
            "id": team.id,
            "team_name": team.team_name,
            "registration_id": team.registration_id,
            "college": team.college,
            "leader_name": team.leader_name,
            "leader_email": team.leader_email,
            "payment_status": team.payment_status,
            "registration_status": team.registration_status,
            "zip_download_url": f"/api/certificates/team/{team.id}/zip"
        },
        "matched_member_id": matched_member_id,
        "members": members_list,
        "total_members": len(members_list)
    }


@router.get("/member/{member_id}")
def download_member_certificate_public(
    member_id: str,
    preview: bool = Query(False, description="Set true to stream inline for PDF preview instead of force download"),
    db: Session = Depends(get_db)
):
    """
    Public direct download of individual student certificate PDF.
    """
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Student record not found.")

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
        issue_date=getattr(setting, "cert_issue_date", "September 2026")
    )

    clean_name = "".join(c for c in member.full_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    reg_suffix = team.registration_id if team else "SIH"
    filename = f"Certificate_{clean_name}_{reg_suffix}.pdf"

    disposition = f'inline; filename="{filename}"' if preview else f'attachment; filename="{filename}"'

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/team/{team_id}/zip")
def download_team_certificates_zip_public(
    team_id: str,
    db: Session = Depends(get_db)
):
    """
    Public direct download of entire team's certificates packaged in a ZIP archive.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team record not found.")

    if not team.members:
        raise HTTPException(status_code=400, detail="Team has no registered members to generate certificates for.")

    setting = db.query(Setting).filter(Setting.id == "registration").first()
    zip_bytes = generate_team_certificates_zip_bytes(team, setting)

    clean_team_name = "".join(c for c in team.team_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    reg_suffix = team.registration_id or "SIH"
    zip_filename = f"Team_Certificates_{clean_team_name}_{reg_suffix}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/custom-download")
@router.get("/download-custom")
def download_custom_certificate(
    student_name: str = Query(..., description="Student/Participant full name"),
    team_name: str = Query("", description="Team Name"),
    college_name: str = Query("", description="College/Institution Name"),
    role: str = Query("Participant", description="Role: Leader / Member / Participant"),
    cert_type: str = Query("Participation", description="Certificate Type"),
    preview: bool = Query(False, description="Set true for inline preview"),
    db: Session = Depends(get_db)
):
    """
    Download a single customized certificate with arbitrary parameters.
    """
    setting = db.query(Setting).filter(Setting.id == "registration").first()
    pdf_bytes = generate_single_certificate_bytes(
        student_name=student_name,
        team_name=team_name,
        college_name=college_name,
        role=role,
        cert_type=cert_type,
        event_title=getattr(setting, "cert_event_title", "Smart India Hackathon 2026 (Internal Hackathon)"),
        sign_1_title=getattr(setting, "cert_sign_1_title", "Convener, Innovation Cell"),
        sign_1_name=getattr(setting, "cert_sign_1_name", "SIH SPOC / Coordinator"),
        sign_2_title=getattr(setting, "cert_sign_2_title", "Head of Institution"),
        sign_2_name=getattr(setting, "cert_sign_2_name", "Principal / Director"),
        issue_date=getattr(setting, "cert_issue_date", "September 2026")
    )

    clean_name = "".join(c for c in student_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    filename = f"Certificate_{clean_name}.pdf"
    disposition = f'inline; filename="{filename}"' if preview else f'attachment; filename="{filename}"'

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
