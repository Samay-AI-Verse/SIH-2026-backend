import os
import sys
import uuid
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.r2_storage import is_r2_configured, get_s3_client, generate_presigned_upload_url, generate_presigned_download_url
from app.database import engine, SessionLocal
from sqlalchemy import text

def print_banner():
    print("=" * 70)
    print(" SIH 2026 BACKEND & CLOUDFLARE R2 ENVIRONMENT TESTER")
    print("=" * 70)

def test_config():
    print_banner()

    # 1. Test .env Basic Settings
    print("\n[1/5] Checking General .env Configuration...")
    print(f"  * App Name: {settings.APP_NAME}")
    print(f"  * Debug Mode: {settings.DEBUG}")
    print(f"  * Admin Email: {settings.ADMIN_EMAIL}")
    print(f"  * Secret Key Set: {'[PASS] Yes' if settings.SECRET_KEY else '[FAIL] Missing'}")

    # 2. Test Database Connection
    print("\n[2/5] Testing SQLite Database Connection...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM teams;")).fetchone()
            print(f"  [PASS] Database Connected! Total Registered Teams in DB: {result[0]}")
    except Exception as e:
        print(f"  [FAIL] Database Error: {e}")

    # 3. Test R2 Configuration Presence
    print("\n[3/5] Checking Cloudflare R2 Environment Variables...")
    print(f"  * R2_ACCOUNT_ID: {settings.R2_ACCOUNT_ID or '[FAIL] Not Set'}")
    print(f"  * R2_ACCESS_KEY_ID: {settings.R2_ACCESS_KEY_ID[:8]}... (Configured)" if settings.R2_ACCESS_KEY_ID else "  * R2_ACCESS_KEY_ID: [FAIL] Not Set")
    print(f"  * R2_SECRET_ACCESS_KEY: {'[PASS] Configured' if settings.R2_SECRET_ACCESS_KEY else '[FAIL] Not Set'}")
    print(f"  * R2_BUCKET: {settings.R2_BUCKET or '[FAIL] Not Set'}")
    print(f"  * R2_PUBLIC_DOMAIN: {settings.R2_PUBLIC_DOMAIN or '[INFO] Not set (will use signed URLs)'}")

    if not is_r2_configured():
        print("\n[FAIL] Cloudflare R2 is NOT fully configured in .env!")
        print("  Backend will fallback to local folder uploads (/uploads).")
        return

    # 4. Test R2 Live Connection & Bucket Access via boto3
    print("\n[4/5] Testing Live Cloudflare R2 Bucket Connection...")
    client = get_s3_client()
    if not client:
        print("  [FAIL] Failed to create boto3 S3 client.")
        return

    try:
        # Check bucket head
        client.head_bucket(Bucket=settings.R2_BUCKET)
        print(f"  [PASS] Successfully connected to Cloudflare R2 Bucket: '{settings.R2_BUCKET}'!")
    except Exception as e:
        print(f"  [FAIL] Cloudflare R2 Bucket Connection Failed: {e}")
        print("  Please double check your R2_ACCOUNT_ID, ACCESS_KEY_ID, SECRET_ACCESS_KEY, and BUCKET name.")
        return

    # 5. Test File Upload, Presigned URL & Cleanup
    print("\n[5/5] Testing Live Object Upload & Presigned URL Generation...")
    test_key = f"tests/ping_{uuid.uuid4().hex[:6]}.txt"
    test_content = b"SIH 2026 Cloudflare R2 Storage Test Ping OK!"

    try:
        # Live Put Object
        client.put_object(
            Bucket=settings.R2_BUCKET,
            Key=test_key,
            Body=test_content,
            ContentType="text/plain"
        )
        print(f"  [PASS] Uploaded test object to R2: '{test_key}'")

        # Test Presigned Upload URL generator
        presigned = generate_presigned_upload_url(test_key, "text/plain")
        print(f"  [PASS] Generated Presigned Upload URL successfully!")
        if presigned.get("public_url"):
            print(f"  [INFO] Public Download URL: {presigned['public_url']}")

        # Clean up test object
        client.delete_object(Bucket=settings.R2_BUCKET, Key=test_key)
        print(f"  [PASS] Cleaned up test object from R2.")

        print("\n" + "=" * 70)
        print(" ALL TESTS PASSED! YOUR .ENV AND CLOUDFLARE R2 ARE 100% READY!")
        print("=" * 70)

    except Exception as e:
        print(f"  [FAIL] Upload/Delete Test Failed: {e}")

if __name__ == "__main__":
    test_config()
