import os
import pathlib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .config import settings
from .database import engine, Base, SessionLocal
from .seed_data import seed_database
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
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|http://localhost:\d+|http://127\.0\.0\.1:\d+",
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

@app.on_event("startup")
def startup_event():
    # 1. Create DB Tables
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed Admin & Problem Statements
    db = SessionLocal()
    try:
        seed_database(db)
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
