from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, os, shutil, re, fitz, sqlite3, traceback
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import smtplib
from email.message import EmailMessage

app = FastAPI(title="RecruitAI Enterprise ATS")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("app/static", exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- SMTP Credentials ---
SENDER_EMAIL = "mithi.morolia@gmail.com"
SENDER_PASSWORD = "imonewvgzyspoegb"

JOB_ROLES = {
    "Python Developer": "Looking for a Python Developer with strong knowledge of Machine Learning, Natural Language Processing, FastAPI, Scikit-learn, Data Analysis, Git and AI project experience.",
    "Data Analyst": "Looking for a Data Analyst with Python, SQL, Excel, Data Analysis, data visualization, reporting and problem-solving skills.",
    "Frontend Developer": "Looking for a Frontend Developer with HTML, CSS, JavaScript, responsive design and web development projects.",
    "AI ML Intern": "Looking for an AI ML Intern with Python, Machine Learning, Deep Learning, NLP, TensorFlow, Scikit-learn and AI project experience.",
    "Cybersecurity Intern": "Looking for a Cybersecurity Intern with networking, Python, Linux, security tools, ethical hacking basics and problem-solving skills."
}

COMMON_SKILLS = ["python", "machine learning", "nlp", "fastapi", "scikit-learn", "data analysis", "sql", "git", "deep learning", "tensorflow", "html", "css", "javascript", "excel", "linux", "networking", "cybersecurity"]

def init_db():
    conn = sqlite3.connect("resume_screening.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS screening_results (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_name TEXT, candidate_email TEXT, resume_filename TEXT, saved_path TEXT, job_role TEXT, job_match_score REAL, integrity_score REAL, final_score REAL, matched_skills TEXT, missing_skills TEXT, status TEXT, hr_decision TEXT, explanation TEXT, integrity_notes TEXT, suggestions TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS system_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_text TEXT, timestamp TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS communications (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_name TEXT, candidate_email TEXT, role TEXT, decision TEXT, timestamp TEXT)")
    conn.commit(); conn.close()

def log_audit(msg):
    conn = sqlite3.connect("resume_screening.db"); cur = conn.cursor()
    cur.execute("INSERT INTO system_logs (log_text, timestamp) VALUES (?, ?)", (msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def log_comm(name, email, role, decision):
    conn = sqlite3.connect("resume_screening.db"); cur = conn.cursor()
    cur.execute("INSERT INTO communications (candidate_name, candidate_email, role, decision, timestamp) VALUES (?, ?, ?, ?, ?)", (name, email, role, decision, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def save_result(result):
    conn = sqlite3.connect("resume_screening.db"); cur = conn.cursor()
    cur.execute("INSERT INTO screening_results (candidate_name, candidate_email, resume_filename, saved_path, job_role, job_match_score, integrity_score, final_score, matched_skills, missing_skills, status, hr_decision, explanation, integrity_notes, suggestions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                (result["name"], result["email"], result["resume_filename"], result["saved_path"], result["job_role"], result["job_match_score"], result["integrity_score"], result["final_score"], ", ".join(result["matched_skills"]), ", ".join(result["missing_skills"]), result["status"], result["hr_decision"], result["explanation"], "; ".join(result["integrity_notes"]), "; ".join(result["suggestions"]), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def preprocess(text):
    text = text.lower()
    cleaned = "".join([c if c.isalpha() or c.isspace() else " " for c in text])
    stopwords = {"the", "is", "are", "a", "an", "and", "or", "to", "of", "in", "for", "with", "on", "by", "this", "that", "good", "strong"}
    return " ".join([w for w in cleaned.split() if w not in stopwords and len(w) > 1])

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc: text += page.get_text() + " \n "
        doc.close()
    except Exception: pass
    return text

def calculate_integrity_score(text):
    lower = text.lower()
    score, notes = 0, []
    if re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text): score += 20; notes.append("Email present")
    else: notes.append("Email missing")
    if re.search(r"(\+?\d[\d\s\-]{8,}\d)", text): score += 20; notes.append("Phone present")
    else: notes.append("Phone missing")
    found = [sec.title() for sec in ["education", "skills", "projects", "experience"] if sec in lower]
    score += len(found) * 10
    notes.append("Sections found: " + ", ".join(found) if found else "Important sections missing")
    if len(text.split()) > 40: score += 20; notes.append("Detailed content")
    else: notes.append("Content too short")
    return max(0, min(score, 100)), notes

def matched_and_missing_skills(jd, resume):
    jd_lower, res_lower = jd.lower(), resume.lower()
    matched, missing = [], []
    required = [s for s in COMMON_SKILLS if s in jd_lower]
    for skill in required:
        if skill in res_lower: matched.append(skill.title())
        else: missing.append(skill.title())
    return matched, missing

def generate_status(final_score, integrity_score):
    if final_score >= 70 and integrity_score >= 60: return "Shortlisted"
    elif final_score >= 45: return "Review Manually"
    return "Rejected"

def generate_resume_suggestions(missing_skills, integrity_notes):
    suggestions = []
    for skill in missing_skills: suggestions.append(f"Consider acquiring {skill} skills.")
    notes_text = " ".join(integrity_notes).lower()
    if "email missing" in notes_text: suggestions.append("Add a professional email address.")
    if "phone missing" in notes_text: suggestions.append("Add a valid phone number.")
    if "too short" in notes_text: suggestions.append("Expand on projects, skills, and experience.")
    if not suggestions: suggestions.append("Resume is robust and well-structured.")
    return suggestions

def dispatch_automated_email(email, name, role, decision, time_val):
    msg = EmailMessage()
    msg['Subject'] = f"Update on your application for {role} at TITAN"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    
    display_time = time_val.replace('T', ' at ') if time_val else "a time to be confirmed"
    
    if "Interview" in decision:
        body = f"Dear {name},\n\nCongratulations! We are pleased to invite you to an interview for the {role} position.\n\nYour interview has been scheduled for:\n📅 {display_time}\n\nPlease prepare accordingly and let us know if you have any questions.\n\nBest regards,\nHR Team | TITAN ATS"
    elif "Hold" in decision:
        body = f"Dear {name},\n\nYour application for the {role} position is currently under review and has been placed on hold. We will update you shortly.\n\nBest regards,\nHR Team | TITAN ATS"
    else:
        body = f"Dear {name},\n\nThank you for applying for the {role} position. After careful review, we have decided to move forward with other candidates at this time.\n\nWe wish you the best in your job search.\n\nBest regards,\nHR Team | TITAN ATS"
    
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        log_audit(f"✅ Email successfully delivered to {email}")
    except Exception as e:
        log_audit(f"❌ Email Failed for {name}: {str(e)}")

@app.get("/")
def dashboard(): return FileResponse("app/static/index.html")

@app.get("/careers")
def careers(): return FileResponse("app/static/careers.html")

@app.get("/preview/{filename}")
def preview_resume(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path): return {"error": "File not found"}
    return FileResponse(file_path, media_type="application/pdf", filename=filename)

@app.post("/apply")
async def apply(name: str = Form(...), email: str = Form(...), role: str = Form(...), resumes: list[UploadFile] = File(...)):
    try:
        jd_text = JOB_ROLES.get(role, f"Looking for a professional with expertise in {role}.")
        jd_processed = preprocess(jd_text)
        saved_count = 0
        
        for resume in resumes:
            if not resume.filename.lower().endswith(".pdf"): continue
            
            safe_name = f"{datetime.now().strftime('%f')}_{resume.filename.replace(' ', '_')}"
            file_path = os.path.join(UPLOAD_FOLDER, safe_name)
            with open(file_path, "wb") as buffer: shutil.copyfileobj(resume.file, buffer)
            
            text = extract_text_from_pdf(file_path)
            if not text.strip(): return {"error": f"Could not extract text from {resume.filename}."}
            
            resume_processed = preprocess(text)
            if not resume_processed.strip(): return {"error": f"Resume {resume.filename} contains no readable keywords."}

            vectorizer = TfidfVectorizer()
            vectors = vectorizer.fit_transform([jd_processed, resume_processed])
            job_score = round(float(cosine_similarity(vectors[0:1], vectors[1:2])[0][0]) * 100, 2)
            
            integrity_score, notes = calculate_integrity_score(text)
            matched, missing = matched_and_missing_skills(jd_text, text)
            
            final_score = round((0.70 * job_score) + (0.30 * integrity_score), 2)
            status = generate_status(final_score, integrity_score)
            
            explanation = "Strong match." if status == "Shortlisted" else ("Missing required skills." if missing else "Needs manual review.")
            suggestions = generate_resume_suggestions(missing, notes)

            result = {
                "name": name, "email": email, "resume_filename": safe_name, "saved_path": file_path, 
                "job_role": role, "job_match_score": job_score, "integrity_score": integrity_score, 
                "final_score": final_score, "matched_skills": matched, "missing_skills": missing, 
                "status": status, "hr_decision": "Pending", "explanation": explanation, 
                "integrity_notes": notes, "suggestions": suggestions
            }
            save_result(result)
            log_audit(f"System scanned applicant '{name}' for {role}. Score: {final_score}%")
            saved_count += 1
            
        if saved_count == 0: return {"error": "No valid PDFs were processed."}
        return {"message": "Success"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/api/pipeline")
def get_pipeline(role: str = "All"):
    conn = sqlite3.connect("resume_screening.db"); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    if role == "All": cur.execute("SELECT * FROM screening_results ORDER BY final_score DESC")
    else: cur.execute("SELECT * FROM screening_results WHERE job_role = ? ORDER BY final_score DESC", (role,))
    rows = cur.fetchall(); conn.close()
    return {"candidates": [dict(r) for r in rows]}

@app.get("/api/logs")
def get_logs():
    conn = sqlite3.connect("resume_screening.db"); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    cur.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall(); conn.close()
    return {"logs": [dict(r) for r in rows]}

@app.get("/api/comms")
def get_comms():
    conn = sqlite3.connect("resume_screening.db"); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    cur.execute("SELECT * FROM communications ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall(); conn.close()
    return {"comms": [dict(r) for r in rows]}

@app.post("/update-decision")
def update_decision(candidate_id: int = Form(...), decision: str = Form(...), time: str = Form(""), email: str = Form(...), name: str = Form(...), role: str = Form(...), bg_tasks: BackgroundTasks = BackgroundTasks()):
    conn = sqlite3.connect("resume_screening.db"); cur = conn.cursor()
    final_status = f"Interview on {time.replace('T', ' ')}" if time else decision
    cur.execute("UPDATE screening_results SET hr_decision = ? WHERE id = ?", (final_status, candidate_id))
    conn.commit(); conn.close()
    log_audit(f"HR decision for {name}: {final_status}")
    log_comm(name, email, role, final_status)
    bg_tasks.add_task(dispatch_automated_email, email, name, role, decision, time)
    return {"message": "Success"}

if __name__ == "__main__":
    init_db(); uvicorn.run(app, host="127.0.0.1", port=8000)