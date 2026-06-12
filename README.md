# TITAN ATS: Enterprise AI Recruitment Assistant

## Abstract

TITAN ATS is an intelligent, end-to-end Applicant Tracking System (ATS) developed to optimize and modernize the recruitment lifecycle. By leveraging Natural Language Processing (NLP), Machine Learning (ML), and rule-based evaluation mechanisms, the system automates resume screening, evaluates candidate integrity, identifies skill gaps, and supports data-driven decision-making for Human Resource professionals.

The platform significantly reduces manual effort, minimizes hiring bias, improves candidate shortlisting accuracy, and enhances the overall efficiency of the recruitment pipeline through intelligent automation and real-time analytics.

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

Provides administrators with real-time analytics, candidate filtering, interview scheduling, HR workflow management, and export functionality for reports in CSV and PDF formats.

---

## Technology Stack

## Backend and AI Processing

* **Programming Language:** Python 3
* **Framework:** FastAPI
* **Server:** Uvicorn
* **Machine Learning / NLP:** Scikit-learn, spaCy
* **Document Parsing:** PyMuPDF (`fitz`)
* **Database:** SQLite3

---

## Frontend and User Interface

* **Structure:** HTML5
* **Styling:** CSS3
* **Interactivity:** JavaScript (Vanilla JS)
* **Data Visualization:** Chart.js

---

## Installation and Setup

## 1. Prerequisites

Ensure the following software is installed on the local system:

* Python 3.9 or above
* Git
* pip package manager

---

## 2. Clone the Repository

```bash
git clone https://github.com/Mahi0510/PBL-2-Mini-Project.git
cd PBL-2-Mini-Project
```

---

## 3. Install Required Dependencies

It is recommended to create and activate a virtual environment before installation.

```bash
pip install -r requirements.txt
```

---

## 4. Install NLP Language Model

Download the required English language model for spaCy:

```bash
python -m spacy download en_core_web_sm
```

---

## Usage Instructions

## Starting the Backend Server

Navigate to the project root directory and execute:

```bash
python app/main.py
```

This will launch the FastAPI backend server on:

```text
http://127.0.0.1:8000
```

---

## Accessing the HR Portal

Open a web browser and navigate to:

```text
http://127.0.0.1:8000
```

Use the administrator login credentials:

* **Username:** admin
* **Password:** admin123

---

## Operational Workflow

### Step 1: Resume Screening

Select the target job role or enter a custom job description and upload candidate PDF resumes in bulk.

### Step 2: AI-Based Evaluation

The system calculates:

* Job Match Score
* Integrity Score
* Final Ranking Score
* Missing Skills Analysis
* Improvement Suggestions

### Step 3: HR Decision Making

HR can update candidate status as:

* Selected
* Hold
* Rejected

### Step 4: Interview Scheduling

For shortlisted candidates, HR can schedule interviews by selecting date and time slots directly from the dashboard.

### Step 5: Automated Communication

System automatically generates and sends professional emails and HR letters based on candidate status.

---

## Project Structure

```text
PBL-2-Mini-Project/
│
├── app/
│   │
│   ├── main.py
│   │   → Core FastAPI backend application
│   │   → Resume parsing
│   │   → ML ranking logic
│   │   → Email automation
│   │
│   └── static/
│       │
│       ├── index.html
│       │   → Secure HR Dashboard Interface
│       │
│       └── careers.html
│           → Public-facing Candidate Application Portal
│
├── uploads/
│   → Temporary storage for uploaded resume PDFs
│
├── resume_screening.db
│   → SQLite relational database
│
├── requirements.txt
│   → Python package dependencies
│
└── README.md
    → Project documentation
```

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
