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
    admin = db.query(Admin).filter(Admin.email == email_clean).first()
    
    ip_addr = extract_client_ip(request)
    user_agent = request.headers.get("User-Agent", "Unknown Browser")
    
    if not admin or not verify_password(req.password, admin.password_hash):
        # Record Failed Login Audit Log
        try:
            log_entry = AdminLoginLog(
                admin_id=admin.id if admin else None,
                email=email_clean,
                name=admin.name if admin else "Unknown User",
                role=admin.role if admin else "UNAUTHORIZED",
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
            detail="Incorrect email or password",
        )
    
    # Record Successful Login Audit Log
    try:
        log_entry = AdminLoginLog(
            admin_id=admin.id,
            email=admin.email,
            name=admin.name,
            role=admin.role,
            ip_address=ip_addr,
            user_agent=user_agent,
            status="SUCCESS"
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()

    access_token = create_access_token(data={"sub": admin.email, "role": admin.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": {
            "id": admin.id,
            "email": admin.email,
            "name": admin.name,
            "role": admin.role
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
            "role": current_admin.role
        }
    }

