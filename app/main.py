import os
import pathlib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .config import settings
from .database import engine, Base, SessionLocal
from .seed_data import seed_database
from .d1_sync import pull_from_d1_to_sqlite
from .routers import auth, teams, dashboard, problems, payments, admin, live

# Initialize FastAPI App
app = FastAPI(
    title=settings.APP_NAME,
    description="FastAPI Backend for SIH 2026 Hackathon Portal with Cloudflare R2 & D1 Integration",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
cors_origins = settings.CORS_ORIGINS
if isinstance(cors_origins, str):
    cors_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ensure uploads directory exists
UPLOAD_DIR = pathlib.Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Include Routers
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(dashboard.router)
app.include_router(problems.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(live.router)

def run_migrations():
    """Ensure newly added columns exist in existing SQLite database tables."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Team table columns
        team_columns = [
            ("entry_status", "TEXT DEFAULT 'PENDING'"),
            ("checked_in_at", "TEXT"),
            ("checked_in_by", "TEXT"),
            ("desk_number", "TEXT"),
            ("goodies_status", "TEXT DEFAULT 'PENDING'"),
            ("goodies_count", "INTEGER DEFAULT 0"),
            ("goodies_collected_at", "TEXT"),
            ("goodies_distributed_by", "TEXT"),
            ("checkin_notes", "TEXT DEFAULT ''"),
            ("present_members_count", "INTEGER DEFAULT 0"),
            ("present_member_ids", "TEXT DEFAULT '[]'"),
        ]
        for col_name, col_type in team_columns:
            try:
                conn.execute(text(f"ALTER TABLE teams ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            except Exception:
                pass # Column already exists

        # Member table columns
        member_columns = [
            ("entry_status", "TEXT DEFAULT 'PENDING'"),
            ("checked_in_at", "TEXT"),
            ("goodies_received", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in member_columns:
            try:
                conn.execute(text(f"ALTER TABLE members ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            except Exception:
                pass # Column already exists

@app.on_event("startup")
def startup_event():
    # 1. Ensure all models are registered and create tables
    from . import models
    Base.metadata.create_all(bind=engine)
    run_migrations()
    
    # 2. Seed Admin & Problem Statements
    db = SessionLocal()
    try:
        seed_database(db)
        # 3. Auto-pull all records from Cloudflare D1 Cloud Database into local SQLite
        pull_from_d1_to_sqlite(db)
    finally:
        db.close()

@app.get("/")
def root():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "docs": "/docs",
        "cloudflare_r2_enabled": bool(settings.R2_ACCOUNT_ID and settings.R2_BUCKET)
    }

@app.get("/api/settings")
def get_settings():
    db = SessionLocal()
    try:
        from .models import Setting
        s = db.query(Setting).filter(Setting.id == "registration").first()
        return {
            "fee": s.fee if s else 300.0,
            "currency": s.currency if s else "INR",
            "isActive": s.is_active if s else True,
            "minMembers": s.min_members if s else 6,
            "maxMembers": s.max_members if s else 6,
            "femaleRequired": s.female_required if s else True
        }
    finally:
        db.close()

@app.post("/api/contact")
def submit_contact(data: dict):
    return {"success": True, "message": "Thank you! We have received your query."}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "Internal server error occurred"}
    )
