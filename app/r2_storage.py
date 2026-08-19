import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any
from .config import settings

def is_r2_configured() -> bool:
    return bool(
        settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET
    )

def get_s3_client():
    if not is_r2_configured():
        return None
    endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4")
    )

def generate_presigned_upload_url(key: str, content_type: str = "image/jpeg", expires_in: int = 300) -> Dict[str, Any]:
    """
    Generates a presigned PUT URL for direct frontend-to-Cloudflare-R2 upload.
    If R2 is not configured, returns direct local upload endpoint URL.
    """
    if is_r2_configured():
        client = get_s3_client()
        try:
            url = client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": settings.R2_BUCKET,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            public_url = (
                f"{settings.R2_PUBLIC_DOMAIN.rstrip('/')}/{key}"
                if settings.R2_PUBLIC_DOMAIN
                else None
            )
            return {
                "upload_url": url,
                "key": key,
                "storage_type": "cloudflare_r2",
                "public_url": public_url
            }
        except ClientError as e:
            raise RuntimeError(f"Cloudflare R2 error: {str(e)}")
    else:
        # Fallback local storage endpoint
        return {
            "upload_url": f"/api/payments/upload-direct?key={key}",
            "key": key,
            "storage_type": "local",
            "public_url": f"/uploads/{key}"
        }

def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """
    Generates a secure temporary signed download URL for viewing payment receipts/proofs.
    """
    if is_r2_configured():
        if settings.R2_PUBLIC_DOMAIN:
            return f"{settings.R2_PUBLIC_DOMAIN.rstrip('/')}/{key}"
        client = get_s3_client()
        try:
            return client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.R2_BUCKET, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError:
            return ""
    else:
        return f"/uploads/{key}"
