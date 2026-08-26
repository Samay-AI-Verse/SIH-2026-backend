from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Admin, AdminLoginLog
from ..schemas import AdminLoginRequest, AdminTokenResponse
from ..auth import verify_password, create_access_token, get_current_admin

router = APIRouter(tags=["Admin Auth"])

def extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/api/auth/login", response_model=AdminTokenResponse)
@router.post("/api/admin/login", response_model=AdminTokenResponse)
def login(req: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = req.email.lower().strip()
    google_mail = req.google_email.lower().strip() if req.google_email else None
    ip_addr = extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "Unknown")
    
    # Query admin by registered email or linked google_email
    admin = db.query(Admin).filter(
        (Admin.email == email_clean) | (Admin.google_email == email_clean)
    ).first()
    if not admin and google_mail:
        admin = db.query(Admin).filter(Admin.google_email == google_mail).first()

    # Self-healing check for Master Admin & Coordinator default credentials
    is_valid = False
    if admin and verify_password(req.password, admin.password_hash):
        is_valid = True
    elif email_clean in ["sih@gtmcnanded.in", "samaypowade1@gmail.com"] and req.password == "SIH@2026@TEAM":
        if not admin:
            admin = Admin(
                email=email_clean,
                name="SIH Master Admin",
                role="SUPER_ADMIN",
                google_email=google_mail or "samaypowade1@gmail.com",
                password_hash=get_password_hash("SIH@2026@TEAM"),
                token_version=100
            )
            db.add(admin)
        else:
            admin.password_hash = get_password_hash("SIH@2026@TEAM")
            admin.role = "SUPER_ADMIN"
            if google_mail:
                admin.google_email = google_mail
        db.commit()
        db.refresh(admin)
        is_valid = True
    elif email_clean == "admin@gtmcnanded.in" and req.password == "SIH@2026@2026":
        if not admin:
            admin = Admin(
                email=email_clean,
                name="SIH Coordinator",
                role="ADMIN",
                google_email=google_mail,
                password_hash=get_password_hash("SIH@2026@2026"),
                token_version=100
            )
            db.add(admin)
        else:
            admin.password_hash = get_password_hash("SIH@2026@2026")
            admin.role = "ADMIN"
            if google_mail:
                admin.google_email = google_mail
        db.commit()
        db.refresh(admin)
        is_valid = True

    if not is_valid or not admin:
        # Record Failed Login Audit Log
        try:
            log_entry = AdminLoginLog(
                admin_id=admin.id if admin else None,
                email=email_clean,
                name=admin.name if admin else "Unknown User",
                role=admin.role if admin else "UNAUTHORIZED",
                google_email=google_mail,
                ip_address=ip_addr,
                user_agent=user_agent,
                status="FAILED"
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin ID or password",
        )
    
    # Record Successful Login Audit Log and update admin last login
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).isoformat()
    if google_mail:
        admin.google_email = google_mail
    admin.last_login_at = now_str

    try:
        log_entry = AdminLoginLog(
            admin_id=admin.id,
            email=admin.email,
            name=admin.name,
            role=admin.role,
            google_email=google_mail or admin.google_email,
            ip_address=ip_addr,
            user_agent=user_agent,
            status="SUCCESS"
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()

    token_version = getattr(admin, "token_version", 1) or 1
    access_token = create_access_token(data={"sub": admin.email, "role": admin.role, "ver": token_version})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": {
            "id": admin.id,
            "email": admin.email,
            "name": admin.name,
            "role": admin.role,
            "google_email": admin.google_email,
            "created_by": getattr(admin, "created_by", "MASTER_ADMIN"),
            "last_login_at": admin.last_login_at
        }
    }

@router.get("/api/admin/me")
@router.get("/api/auth/me")
def get_current_admin_info(current_admin: Admin = Depends(get_current_admin)):
    return {
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "name": current_admin.name,
            "role": current_admin.role,
            "google_email": getattr(current_admin, "google_email", None),
            "created_by": getattr(current_admin, "created_by", "MASTER_ADMIN"),
            "last_login_at": getattr(current_admin, "last_login_at", None)
        }
    }

