from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Admin
from ..schemas import AdminLoginRequest, AdminTokenResponse
from ..auth import verify_password, create_access_token, get_current_admin

router = APIRouter(tags=["Admin Auth"])

@router.post("/api/auth/login", response_model=AdminTokenResponse)
@router.post("/api/admin/login", response_model=AdminTokenResponse)
def login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    email_clean = req.email.lower().strip()
    admin = db.query(Admin).filter(Admin.email == email_clean).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
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
