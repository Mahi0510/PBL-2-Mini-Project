"""TITAN ATS - AI-assisted resume screening (FastAPI + SQLite)."""
import asyncio
import hashlib
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))            # lets `python app/main.py` find the `app` package

try:
    import pymupdf                       # PyMuPDF >= 1.24
except ImportError:                      # older installs
    import fitz as pymupdf
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import scoring

# ---------------------------------------------------------------- configuration
load_dotenv(ROOT / ".env")
STATIC_DIR = ROOT / "app" / "static"


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


DB_PATH = ROOT / os.getenv("DATABASE_PATH", "resume_screening.db")
UPLOAD_DIR = ROOT / os.getenv("UPLOAD_DIR", "uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

COMPANY_NAME = os.getenv("COMPANY_NAME", "TITAN")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", f"{COMPANY_NAME} HR Team")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(10)
    print(f"[TITAN ATS] ADMIN_PASSWORD not set - temporary password for this run: {ADMIN_PASSWORD}")

SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))
COOKIE_SECURE = env_bool("COOKIE_SECURE", False)     # set true when served over HTTPS
TRUST_PROXY = env_bool("TRUST_PROXY", False)         # true only behind your own reverse proxy
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "365"))   # 0 = keep forever
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("titan")

DEFAULT_ROLES = {
    "Python Developer": "Looking for a Python Developer with strong knowledge of Machine Learning, Natural Language Processing, FastAPI, Scikit-learn, Data Analysis, Git and AI project experience.",
    "Data Analyst": "Looking for a Data Analyst with Python, SQL, Excel, Data Analysis, data visualization, reporting and problem-solving skills.",
    "Frontend Developer": "Looking for a Frontend Developer with HTML, CSS, JavaScript, responsive design and web development projects.",
    "AI ML Intern": "Looking for an AI ML Intern with Python, Machine Learning, Deep Learning, NLP, TensorFlow, Scikit-learn and AI project experience.",
    "Cybersecurity Intern": "Looking for a Cybersecurity Intern with networking, Python, Linux, security tools, ethical hacking basics and problem-solving skills.",
}


# ---------------------------------------------------------------- database
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE IF NOT EXISTS screening_results (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_name TEXT, candidate_email TEXT, resume_filename TEXT, saved_path TEXT, job_role TEXT, job_match_score REAL, integrity_score REAL, final_score REAL, matched_skills TEXT, missing_skills TEXT, status TEXT, hr_decision TEXT, explanation TEXT, integrity_notes TEXT, suggestions TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS system_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_text TEXT, timestamp TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS communications (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_name TEXT, candidate_email TEXT, role TEXT, decision TEXT, timestamp TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS job_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT UNIQUE NOT NULL, description TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL)")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(screening_results)")}
        if "consent_at" not in cols:                       # migration for databases created by older versions
            c.execute("ALTER TABLE screening_results ADD COLUMN consent_at TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_results_role ON screening_results(job_role)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_results_email ON screening_results(candidate_email, job_role)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_results_created ON screening_results(created_at)")
        if c.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0:
            c.executemany("INSERT INTO job_roles (title, description, created_at) VALUES (?, ?, ?)",
                          [(t, d, now_str()) for t, d in DEFAULT_ROLES.items()])


def log_audit(msg: str):
    with db() as c:
        c.execute("INSERT INTO system_logs (log_text, timestamp) VALUES (?, ?)", (msg, now_str()))


def log_comm(name, email, role, decision):
    with db() as c:
        c.execute("INSERT INTO communications (candidate_name, candidate_email, role, decision, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (name, email, role, decision, now_str()))


def erase_candidate(conn, row) -> None:
    """Delete one application: database row, communication history and the stored PDF."""
    (UPLOAD_DIR / Path(row["resume_filename"]).name).unlink(missing_ok=True)
    conn.execute("DELETE FROM communications WHERE candidate_email = ? AND role = ?", (row["candidate_email"], row["job_role"]))
    conn.execute("DELETE FROM screening_results WHERE id = ?", (row["id"],))


def purge_old(days: int) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db() as c:
        rows = c.execute("SELECT id, resume_filename, candidate_email, job_role FROM screening_results WHERE created_at < ?", (cutoff,)).fetchall()
        for r in rows:
            erase_candidate(c, r)
    if rows:
        log_audit(f"Retention policy: removed {len(rows)} application(s) older than {days} days")
    return len(rows)


# ---------------------------------------------------------------- sessions + rate limiting
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        c.execute("INSERT INTO sessions (token_hash, expires_at) VALUES (?, ?)", (_hash(token), time.time() + SESSION_HOURS * 3600))
    return token


def require_admin(session: Optional[str] = Cookie(default=None)):
    if session:
        with db() as c:
            if c.execute("SELECT 1 FROM sessions WHERE token_hash = ? AND expires_at > ?", (_hash(session), time.time())).fetchone():
                return
    raise HTTPException(status_code=401, detail="Not authenticated")


class RateLimiter:
    """Sliding-window limiter (in-memory; run a single worker, as the Dockerfile does)."""
    def __init__(self, limit: int, window_s: int):
        self.limit, self.window, self.hits = limit, window_s, defaultdict(deque)

    def _prune(self, key):
        dq, now = self.hits[key], time.time()
        while dq and now - dq[0] > self.window:
            dq.popleft()
        return dq

    def allowed(self, key) -> bool:
        return len(self._prune(key)) < self.limit

    def record(self, key):
        self._prune(key).append(time.time())

    def clear(self):
        self.hits.clear()


login_limiter = RateLimiter(limit=5, window_s=600)       # 5 failed logins / 10 min / IP
apply_limiter = RateLimiter(limit=10, window_s=3600)     # 10 applications / hour / IP


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- email
def dispatch_automated_email(name: str, email: str, role: str, decision: str, status_text: str, when: Optional[datetime]):
    if not (SMTP_USER and SMTP_PASSWORD):
        log_audit(f"⚠️ Email NOT sent to {email}: SMTP is not configured")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Update on your application for {role} at {COMPANY_NAME}"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = email
    sign = f"Best regards,\n{SMTP_FROM_NAME}"
    if decision == "Interview Scheduled" and when:
        body = (f"Dear {name},\n\nWe are pleased to invite you to an interview for the {role} position.\n\n"
                f"Your interview is scheduled for:\n{when.strftime('%A, %d %B %Y at %I:%M %p')}\n\n"
                f"Please reply to this email if you need to reschedule.\n\n{sign}")
    elif decision == "Hold":
        body = (f"Dear {name},\n\nYour application for the {role} position is still under review. "
                f"We will update you as soon as we can.\n\n{sign}")
    else:
        body = (f"Dear {name},\n\nThank you for applying for the {role} position. After careful review by our team, "
                f"we have decided to move forward with other candidates at this time.\n\nWe wish you the best in your job search.\n\n{sign}")
    msg.set_content(body)
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.login(SMTP_USER, SMTP_PASSWORD); s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls(); s.login(SMTP_USER, SMTP_PASSWORD); s.send_message(msg)
        log_audit(f"✅ Email successfully delivered to {email}")
        log_comm(name, email, role, status_text)
    except Exception as e:
        log.warning("Email failed: %s", e)
        log_audit(f"❌ Email failed for {name}: {e}")


# ---------------------------------------------------------------- app
async def _retention_loop():
    while True:
        await asyncio.sleep(24 * 3600)
        await asyncio.to_thread(purge_old, RETENTION_DAYS)


@asynccontextmanager
async def lifespan(_app):
    init_db()
    task = None
    if RETENTION_DAYS > 0:
        await asyncio.to_thread(purge_old, RETENTION_DAYS)
        task = asyncio.create_task(_retention_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="TITAN ATS", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
                                                    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
    if request.url.path.startswith("/api/") or request.url.path in ("/login", "/logout"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def err(msg: str, code: int = 400):
    return JSONResponse({"error": msg}, status_code=code)


# ---------------------------------------------------------------- auth + misc
@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = client_ip(request)
    if not login_limiter.allowed(ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 10 minutes.")
    ok = (secrets.compare_digest(username.strip().lower().encode(), ADMIN_USERNAME.lower().encode())
          & secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode()))
    if not ok:
        login_limiter.record(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    resp = JSONResponse({"message": "ok"})
    resp.set_cookie("session", create_session(), httponly=True, samesite="lax", secure=COOKIE_SECURE, max_age=SESSION_HOURS * 3600)
    return resp


@app.post("/logout")
def logout(session: Optional[str] = Cookie(default=None)):
    if session:
        with db() as c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(session),))
    resp = JSONResponse({"message": "ok"})
    resp.delete_cookie("session")
    return resp


@app.get("/api/me", dependencies=[Depends(require_admin)])
def me():
    return {"message": "ok"}


@app.get("/health")
def health():
    try:
        with db() as c:
            c.execute("SELECT 1").fetchone()
        return {"status": "ok"}
    except Exception:
        return JSONResponse({"status": "error"}, status_code=503)


@app.get("/api/public-config")
def public_config():
    return {"company": COMPANY_NAME, "retention_days": RETENTION_DAYS}


# ---------------------------------------------------------------- pages
@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/careers")
def careers():
    return FileResponse(STATIC_DIR / "careers.html")


@app.get("/preview/{filename}", dependencies=[Depends(require_admin)])
def preview_resume(filename: str):
    path = UPLOAD_DIR / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


# ---------------------------------------------------------------- job roles
@app.get("/api/roles")
def public_roles():
    with db() as c:
        rows = c.execute("SELECT title FROM job_roles WHERE active = 1 ORDER BY title").fetchall()
    return {"roles": [r["title"] for r in rows]}


@app.get("/api/roles/all", dependencies=[Depends(require_admin)])
def all_roles():
    with db() as c:
        rows = c.execute("SELECT id, title, description, active FROM job_roles ORDER BY title").fetchall()
    return {"roles": [dict(r) for r in rows]}


@app.post("/api/roles", dependencies=[Depends(require_admin)])
def add_role(title: str = Form(...), description: str = Form(...)):
    title, description = title.strip(), description.strip()
    if not 2 <= len(title) <= 80:
        raise HTTPException(status_code=400, detail="Title must be 2-80 characters.")
    if not 30 <= len(description) <= 3000:
        raise HTTPException(status_code=400, detail="Description must be 30-3000 characters; list the skills you require.")
    try:
        with db() as c:
            c.execute("INSERT INTO job_roles (title, description, created_at) VALUES (?, ?, ?)", (title, description, now_str()))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A role with this title already exists.")
    log_audit(f"Job role created: {title}")
    return {"message": "Success", "detected_skills": scoring.skills_in(description)}


@app.post("/api/roles/{role_id}/toggle", dependencies=[Depends(require_admin)])
def toggle_role(role_id: int):
    with db() as c:
        row = c.execute("SELECT title, active FROM job_roles WHERE id = ?", (role_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Role not found.")
        c.execute("UPDATE job_roles SET active = ? WHERE id = ?", (0 if row["active"] else 1, role_id))
    log_audit(f"Job role {'closed' if row['active'] else 'reopened'}: {row['title']}")
    return {"message": "Success"}


# ---------------------------------------------------------------- public: apply
@app.post("/apply")
def apply(request: Request, name: str = Form(...), email: str = Form(...), role: str = Form(...),
          consent: bool = Form(False), resumes: List[UploadFile] = File(...)):
    ip = client_ip(request)
    if not apply_limiter.allowed(ip):
        return err("Too many applications from your network. Please try again later.", 429)
    apply_limiter.record(ip)

    name, email = name.strip(), email.strip()
    if not consent:
        return err("Please accept the privacy notice to apply.")
    if not 1 <= len(name) <= 100:
        return err("Please enter a valid name.")
    if len(email) > 254 or not scoring.EMAIL_RE.fullmatch(email):
        return err("Please enter a valid email address.")
    with db() as c:
        role_row = c.execute("SELECT description FROM job_roles WHERE title = ? AND active = 1", (role,)).fetchone()
        dup = c.execute("SELECT 1 FROM screening_results WHERE lower(candidate_email) = lower(?) AND job_role = ?", (email, role)).fetchone()
    if not role_row:
        return err("This role is not open for applications.")
    if dup:
        return err("You have already applied for this role.", 409)

    saved, problems = 0, []
    for resume in resumes:
        original = resume.filename or "resume.pdf"
        if not original.lower().endswith(".pdf"):
            problems.append(f"{original}: only PDF files are accepted"); continue
        safe = f"{secrets.token_hex(4)}_{re.sub(r'[^A-Za-z0-9._-]', '_', Path(original).name)}"
        path, size = UPLOAD_DIR / safe, 0
        with open(path, "wb") as buf:
            while chunk := resume.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    break
                buf.write(chunk)
        try:
            if size > MAX_UPLOAD_BYTES:
                raise ValueError("larger than 5 MB")
            with open(path, "rb") as f:
                if f.read(5) != b"%PDF-":
                    raise ValueError("not a valid PDF")
            text = ""
            try:
                with pymupdf.open(path) as doc:
                    text = " \n ".join(page.get_text() for page in doc)
            except Exception as e:
                log.warning("PDF read failed (%s): %s", safe, e)
            r = scoring.screen(role_row["description"], text)      # raises ValueError if no readable text
            with db() as c:
                c.execute(
                    "INSERT INTO screening_results (candidate_name, candidate_email, resume_filename, saved_path, job_role, job_match_score, integrity_score, final_score, matched_skills, missing_skills, status, hr_decision, explanation, integrity_notes, suggestions, created_at, consent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (name, email, safe, f"uploads/{safe}", role, r["job_score"], r["integrity_score"], r["final_score"],
                     ", ".join(r["matched"]), ", ".join(r["missing"]), r["status"], "Pending", r["explanation"],
                     "; ".join(r["notes"]), "; ".join(r["suggestions"]), now_str(), now_str()))
            log_audit(f"System scanned applicant '{name}' for {role}. Score: {r['final_score']}%")
            saved += 1
        except ValueError as e:
            path.unlink(missing_ok=True)
            problems.append(f"{original}: {e}")
        except Exception:
            log.exception("Failed processing %s", original)
            path.unlink(missing_ok=True)
            problems.append(f"{original}: processing error")

    if saved == 0:
        return err("No resumes were processed. " + "; ".join(problems))
    return {"message": "Success", "processed": saved, "skipped": problems}


# ---------------------------------------------------------------- HR (login required)
@app.get("/api/pipeline", dependencies=[Depends(require_admin)])
def get_pipeline(role: str = "All"):
    with db() as c:
        if role == "All":
            rows = c.execute("SELECT * FROM screening_results ORDER BY final_score DESC LIMIT 1000").fetchall()
        else:
            rows = c.execute("SELECT * FROM screening_results WHERE job_role = ? ORDER BY final_score DESC LIMIT 1000", (role,)).fetchall()
    return {"candidates": [dict(r) for r in rows]}


@app.get("/api/logs", dependencies=[Depends(require_admin)])
def get_logs():
    with db() as c:
        rows = c.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT 50").fetchall()
    return {"logs": [dict(r) for r in rows]}


@app.get("/api/comms", dependencies=[Depends(require_admin)])
def get_comms():
    with db() as c:
        rows = c.execute("SELECT * FROM communications ORDER BY id DESC LIMIT 50").fetchall()
    return {"comms": [dict(r) for r in rows]}


@app.post("/update-decision", dependencies=[Depends(require_admin)])
def update_decision(bg_tasks: BackgroundTasks, candidate_id: int = Form(...), decision: str = Form(...), time: str = Form("")):
    if decision not in ("Interview Scheduled", "Hold", "Rejected"):
        raise HTTPException(status_code=400, detail="Invalid decision.")
    when = None
    if decision == "Interview Scheduled":
        try:
            when = datetime.fromisoformat(time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Please choose a valid interview date and time.")
        if when < datetime.now():
            raise HTTPException(status_code=400, detail="Interview time cannot be in the past.")
    status_text = f"Interview on {when.strftime('%Y-%m-%d %H:%M')}" if when else decision
    with db() as c:
        row = c.execute("SELECT candidate_name, candidate_email, job_role FROM screening_results WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        c.execute("UPDATE screening_results SET hr_decision = ? WHERE id = ?", (status_text, candidate_id))
    log_audit(f"HR decision for {row['candidate_name']}: {status_text}")
    bg_tasks.add_task(dispatch_automated_email, row["candidate_name"], row["candidate_email"], row["job_role"], decision, status_text, when)
    return {"message": "Success"}


@app.delete("/api/candidates/{candidate_id}", dependencies=[Depends(require_admin)])
def delete_candidate(candidate_id: int):
    """Right-to-erasure: removes the application, its PDF and email history."""
    with db() as c:
        row = c.execute("SELECT id, resume_filename, candidate_email, job_role FROM screening_results WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        erase_candidate(c, row)
    log_audit(f"Candidate record #{candidate_id} permanently deleted (data erasure)")
    return {"message": "Success"}


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
