# Cloudflare Database (D1) & Object Storage (R2) Complete Guide for SIH 2026

## 1. Cloudflare Storage & Free Tier Summary

### A. Cloudflare D1 (SQL Relational Database)
- **What is it?** Cloudflare's serverless SQLite relational database.
- **Free Tier Limits:**
  - **Storage:** **5 GB** database size (Free forever).
  - **Reads:** **5 Million** read rows per day free.
  - **Writes:** **100,000** write rows per day free.
- **Best Use Case:** Storing structured tabular data (Teams, 6 Member rosters, Payments, Problem Statements, Admin users).
- **In our FastAPI Backend:** The backend uses SQLAlchemy ORM with SQLite format which is 100% binary-compatible with Cloudflare D1 and can run locally (`sih_2026.db`) or deployed to Cloudflare D1 / Turso.

---

### B. Cloudflare R2 (Object Storage for Images & Receipts)
- **What is it?** S3-compatible Object Storage for binary files like payment receipts (QR/UPI screenshots), student ID cards, problem statement PDFs, and project presentations.
- **Free Tier Limits:**
  - **Storage:** **10 GB / month free forever**.
  - **Uploads (Class A):** **10 Million** write requests / month free.
  - **Downloads (Class B):** **10 Million** read requests / month free.
  - **Egress Bandwidth:** **$0.00 (Zero Egress Fees forever!)** — Cloudflare never charges for downloading or viewing images.
- **Image Capacity:** At ~500 KB per transaction screenshot, 10 GB gives you capacity for **over 20,000+ high-res images and payment proofs for FREE!**

---

## 2. Step-by-Step: How to Get Cloudflare R2 Keys

### Step 1: Log in to Cloudflare
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) and log in (or create a free account).
2. On the left sidebar, click on **R2** (or **Storage & Databases** -> **R2**).

### Step 2: Create a Storage Bucket
1. Click **Create bucket**.
2. Bucket name: `sih-storage` (or any custom name you prefer).
3. Location: Choose **Automatic** or your nearest region (e.g., APAC / Western Europe).
4. Click **Create Bucket**.

### Step 3: Copy Account ID
- On the right sidebar of the R2 overview page, you will see **Account ID**.
- Copy this 32-character hexadecimal string (e.g. `9f8e7d6c5b4a3...`).

### Step 4: Create API Token
1. On the top right of the R2 page, click **Manage R2 API Tokens**.
2. Click **Create API token**.
3. Set Token Name: `sih-fastapi-backend`.
4. Permissions: Select **Object Read & Write**.
5. Apply to specific bucket: Select `sih-storage` (or all buckets).
6. TTL: Choose *Forever* or as needed.
7. Click **Create API Token**.
8. Copy the credentials displayed on the screen:
   - **Access Key ID** (e.g., `a1b2c3d4e5f6...`)
   - **Secret Access Key** (e.g., `9z8y7x6w5v4u3t2s1r0q...`)

### Step 5: (Optional) Enable Public Bucket Access
1. Go into your bucket `sih-storage` -> **Settings** tab.
2. Scroll to **Public Access** -> **R2.dev subdomain** and click **Allow Access**.
3. Copy the public URL (e.g. `https://pub-xxxxxx.r2.dev`).

---

## 3. Configure Your `.env` in `fastapi_backend/`

Open `fastapi_backend/.env` and paste your Cloudflare keys:

```env
APP_NAME="SIH 2026 Hackathon API"
DEBUG=True
PORT=8000
HOST="0.0.0.0"

# Admin Credentials
ADMIN_EMAIL="sih@gtmcnanded.in"
ADMIN_PASSWORD="SihGtmc2026!"
SECRET_KEY="sih-2026-super-secret-key-change-this"

# Database
DATABASE_URL="sqlite:///./sih_2026.db"

# Cloudflare R2 Credentials
R2_ACCOUNT_ID="your_cloudflare_account_id"
R2_ACCESS_KEY_ID="your_r2_access_key_id"
R2_SECRET_ACCESS_KEY="your_r2_secret_access_key"
R2_BUCKET="sih-storage"
R2_PUBLIC_DOMAIN="https://pub-xxxxxx.r2.dev"
```

*(Note: If you leave the R2 keys blank, the backend automatically uses its built-in local file storage fallback so you can develop offline without any issues!)*

---

## 4. How to Run the Backend

```bash
# Navigate to backend folder
cd "SIH 2026/SIH-Frontend/fastapi_backend"

# Install dependencies (already installed)
pip install -r requirements.txt

# Start the server
python run.py
```

- Server URL: **http://localhost:8000**
- Interactive Swagger API Documentation: **http://localhost:8000/docs**
- Team Dashboard: **http://localhost:5173/dashboard**
- Admin Login: **http://localhost:5173/admin/login** (Email: `sih@gtmcnanded.in`, Password: `SihGtmc2026!`)
