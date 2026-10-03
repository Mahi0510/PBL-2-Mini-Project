# TITAN ATS: Enterprise AI Recruitment Assistant

## Abstract

TITAN ATS is an intelligent, end-to-end Applicant Tracking System (ATS) developed to optimize and modernize the recruitment lifecycle. By leveraging Natural Language Processing (NLP), Machine Learning (ML), and rule-based evaluation mechanisms, the system automates resume screening, evaluates candidate integrity, identifies skill gaps, and supports data-driven decision-making for Human Resource professionals.

The platform significantly reduces manual effort, applies the same screening criteria to every applicant, improves candidate shortlisting accuracy, and enhances the overall efficiency of the recruitment pipeline through intelligent automation and real-time analytics.

---

## Core Features

### 1. Semantic Match Evaluation

Implements TF-IDF (Term Frequency–Inverse Document Frequency) vectorization along with Cosine Similarity to accurately rank candidate resumes against the target job description based on relevance and contextual matching.

### 2. Integrity and Quality Scoring

Uses a rule-based evaluation mechanism to assess resume completeness, detect missing critical information such as contact details, and penalize suspicious keyword stuffing or exaggerated claims.

### 3. Skill Gap Analysis

Automatically compares candidate profiles with industry-standard technical skill requirements to identify exact matches, missing competencies, and improvement recommendations.

### 4. Automated Candidate Communication

Integrates with Google SMTP services to send real-time status-based notifications including Interview Selection, Hold Status, and Rejection emails directly to candidates.

### 5. Persistent Data Management

Utilizes SQLite as the primary relational database to maintain candidate screening history, HR decisions, audit logs, and recruitment workflow records with future scalability toward MySQL/PostgreSQL.

### 6. Interactive HR Analytics Dashboard

Provides administrators with real-time analytics, candidate filtering, interview scheduling, HR workflow management, and CSV export of the candidate pipeline.

---

## Technology Stack

### Backend and AI Processing

* **Programming Language:** Python 3
* **Framework:** FastAPI
* **Server:** Uvicorn
* **Machine Learning / NLP:** Scikit-learn (TF-IDF, cosine similarity)
* **Document Parsing:** PyMuPDF (`fitz`)
* **Configuration:** python-dotenv (`.env`)
* **Database:** SQLite3

### Frontend and User Interface

* **Structure:** HTML5
* **Styling:** CSS3
* **Interactivity:** JavaScript (Vanilla JS)
* **Data Visualization:** Chart.js

---

## Quick Start

**With Docker (production):** see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

**Locally (development):**

```bash
git clone https://github.com/Mahi0510/PBL-2-Mini-Project.git
cd PBL-2-Mini-Project

python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env           # Windows   (macOS/Linux: cp .env.example .env)
# edit .env: set ADMIN_PASSWORD, COMPANY_NAME and SMTP_* values

python app/main.py               # or: uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the HR portal and `http://127.0.0.1:8000/careers` for the public application page. Log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env` (if the password is blank, a temporary one is printed in the console).

Run the tests with `pip install -r requirements-dev.txt` then `python -m pytest`.

---

## How It Works

1. **Candidates apply** on `/careers`: pick an open role, upload PDF resume(s) and accept the privacy notice.
2. **The system scores** each resume: *Job Match* (TF-IDF + cosine similarity against the role description), *Integrity* (contact details, sections, length, keyword-stuffing check), and a weighted *Final Score* (70% match, 30% integrity). Required skills found in the role description are listed as matched or missing.
3. **HR reviews** in the dashboard and chooses **Interview Scheduled**, **Hold** or **Rejected**. An email goes to the candidate and the action is written to the audit log.
4. **HR manages roles** (add, close, reopen), exports the pipeline to CSV, and can permanently delete any candidate's data.

AI scores are advisory only; a human makes every decision. See [docs/COMPLIANCE.md](docs/COMPLIANCE.md).

---

## Project Structure

```text
├── app/
│   ├── main.py          FastAPI app: auth, API, email, retention
│   ├── scoring.py       Resume scoring logic (unit-tested)
│   └── static/
│       ├── index.html   HR dashboard
│       ├── careers.html Public application page
│       └── vendor/      Chart.js (bundled, no CDN needed)
├── tests/               Automated tests (pytest)
├── docs/                DEPLOYMENT.md, COMPLIANCE.md
├── Dockerfile, docker-compose.yml
├── .env.example         Configuration template (copy to .env)
├── requirements.txt, requirements-dev.txt
└── .github/workflows/ci.yml
```

`resume_screening.db` and `uploads/` are created at runtime and are git-ignored.

---

## Security Notes

* Secrets live in `.env` (git-ignored); never hardcode them. If a password was ever committed, revoke it - deleting it from code does not remove it from Git history.
* All HR pages/APIs require login; sessions are server-side and expire; logins and applications are rate-limited.
* Candidate-supplied text is HTML-escaped; uploads are restricted to real PDFs under 5 MB; security headers are set on every response.

---

## Future Scope

### 1. Advanced Semantic Matching

Migration from TF-IDF-based matching to transformer-based NLP models such as BERT for deeper semantic understanding and improved candidate-job relevance scoring.

### 2. Enterprise-Level Database Scaling

Transition from SQLite to MySQL or PostgreSQL for handling large-scale concurrent HR operations and multi-user environments.

### 3. Cloud Deployment

Deployment on cloud platforms such as Render, AWS, or Azure for real-time remote HR collaboration and enterprise accessibility.

### 4. Video Interview Integration

Integration of live video interview scheduling and candidate assessment modules for complete recruitment lifecycle management.

### 5. AI-Powered Fraud Detection

Advanced resume fraud detection using pattern recognition and anomaly detection for improved candidate authenticity verification.

---

## Acknowledgments

This project was developed as part of the Project-Based Learning (PBL) Mini Project submission at:

**MIT World Peace University (MIT-WPU), Pune**

for the academic curriculum of

**B.Tech Computer Science Engineering (Cyber Security and Forensics)**

---

## Developed By
Mahika Morolia


---
