import os
import shutil
import uuid
import pathlib
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Payment, Team
from ..schemas import PaymentUtrSubmitRequest
from ..r2_storage import generate_presigned_upload_url, generate_presigned_download_url, is_r2_configured, get_s3_client
from ..config import settings

router = APIRouter(prefix="/api/payments", tags=["Payments & UTR"])

UPLOAD_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/presign")
def get_upload_presigned_url(
    team_id: str = Query(...),
    content_type: str = Query("image/jpeg")
):
    key = f"proofs/{team_id}-{uuid.uuid4().hex[:8]}.jpg"
    return generate_presigned_upload_url(key=key, content_type=content_type)

@router.post("/upload-direct")
async def upload_direct_file(
    file: UploadFile = File(...),
    key: str = Query(None)
):
    if not key:
        file_ext = os.path.splitext(file.filename)[1] or ".jpg"
        key = f"proofs/{uuid.uuid4().hex[:12]}{file_ext}"

    # Check Cloudflare R2 live storage
    if is_r2_configured():
        client = get_s3_client()
        if client:
            try:
                contents = await file.read()
                client.put_object(
                    Bucket=settings.R2_BUCKET,
                    Key=key,
                    Body=contents,
                    ContentType=file.content_type or "image/jpeg"
                )
                public_url = (
                    f"{settings.R2_PUBLIC_DOMAIN.rstrip('/')}/{key}"
                    if settings.R2_PUBLIC_DOMAIN
                    else generate_presigned_download_url(key)
                )
                return {
                    "success": True,
                    "key": key,
                    "filename": os.path.basename(key),
                    "url": public_url,
                    "storage": "cloudflare_r2"
                }
            except Exception as e:
                # Log and fallback to local storage
                print(f"[R2 Upload Warning] Cloudflare R2 put_object failed, falling back to local: {e}")

    file_path = UPLOAD_DIR / os.path.basename(key)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "success": True,
        "key": key,
        "filename": os.path.basename(key),
        "url": f"/uploads/{os.path.basename(key)}",
        "storage": "local"
    }

@router.post("/utr")
def submit_utr(req: PaymentUtrSubmitRequest, db: Session = Depends(get_db)):
    payment_mode = (req.payment_mode or "ONLINE").upper()
    utr_clean = (req.utr or "").strip().upper()
    collector_clean = (req.collector_name or "").strip()
    receipt_clean = (req.receipt_no or "").strip().upper()
    has_proof = bool(req.proof_url or req.proof_key)

    if payment_mode == "OFFLINE_CASH":
        if not collector_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please specify the Organizing Committee member / coordinator who collected the cash payment."
            )
        if not receipt_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter the Physical Cash Receipt / Token Number issued by the organizer."
            )
        utr_clean = f"OFFLINE-{receipt_clean}"
    else:
        if not utr_clean and not has_proof:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide either a UTR / Transaction ID number or upload a payment screenshot proof."
            )

    # 1. Strict Duplicate Check
    if utr_clean:
        existing_utr = db.query(Payment).filter(
            func.upper(Payment.transaction_id) == utr_clean,
            Payment.team_id != req.team_id
        ).first()
        if existing_utr:
            lbl = f"Offline Cash Receipt '{receipt_clean}'" if payment_mode == "OFFLINE_CASH" else f"UTR / Transaction ID '{utr_clean}'"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This {lbl} has already been submitted for team '{existing_utr.team_name}'. Each team must have a unique receipt."
            )

    # 2. Get Team and Payment Record
    team = db.query(Team).filter(Team.id == req.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team registration not found")

    payment = db.query(Payment).filter(Payment.team_id == team.id).first()
    if not payment:
        payment = Payment(
            team_id=team.id,
            registration_id=team.registration_id,
            team_name=team.team_name,
            order_id=f"ORDER-{team.registration_id}-{uuid.uuid4().hex[:6].upper()}",
            amount=300.0,
            currency="INR"
        )
        db.add(payment)

    # Update payment and team
    payment.payment_mode = payment_mode
    payment.collector_name = collector_clean if payment_mode == "OFFLINE_CASH" else None
    payment.receipt_no = receipt_clean if payment_mode == "OFFLINE_CASH" else None
    payment.transaction_id = utr_clean if utr_clean else f"PROOF-{uuid.uuid4().hex[:8].upper()}"
    payment.status = "PROCESSING"
    if req.proof_key:
        payment.proof_key = req.proof_key
    if req.proof_url:
        payment.proof_url = req.proof_url

    team.payment_status = "PROCESSING"
    team.registration_status = "PENDING_VERIFICATION"
    db.commit()

    return {
        "success": True,
        "message": "Offline cash payment details submitted! Verification is in progress." if payment_mode == "OFFLINE_CASH" else "Payment proof received successfully! Verification is in progress.",
        "team_id": team.id,
        "registration_id": team.registration_id,
        "utr": payment.transaction_id,
        "payment_mode": payment.payment_mode,
        "collector_name": payment.collector_name,
        "receipt_no": payment.receipt_no,
        "status": payment.status
    }
