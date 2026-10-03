"""Resume scoring logic (pure functions - no web or database code, so it is easy to test)."""
import re
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")

JOB_MATCH_WEIGHT = 0.70
INTEGRITY_WEIGHT = 0.30

# display label -> accepted spellings (matched as whole words, case-insensitive)
SKILLS: Dict[str, List[str]] = {
    "Python": ["python"], "Java": ["java"], "JavaScript": ["javascript"], "TypeScript": ["typescript"],
    "C++": ["c++"], "C#": ["c#"], "SQL": ["sql"], "MySQL": ["mysql"], "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb"], "HTML": ["html"], "CSS": ["css"], "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular"], "Node.js": ["node.js", "nodejs", "node js"], "Django": ["django"], "Flask": ["flask"],
    "FastAPI": ["fastapi"], "REST APIs": ["rest api", "rest apis", "restful"], "Git": ["git"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes"], "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"], "GCP": ["gcp", "google cloud"], "Linux": ["linux"], "Networking": ["networking"],
    "Cybersecurity": ["cybersecurity", "cyber security"], "Ethical Hacking": ["ethical hacking"],
    "Penetration Testing": ["penetration testing", "pentesting"],
    "Machine Learning": ["machine learning"], "Deep Learning": ["deep learning"],
    "NLP": ["nlp", "natural language processing"], "Computer Vision": ["computer vision"],
    "TensorFlow": ["tensorflow"], "PyTorch": ["pytorch"], "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "Pandas": ["pandas"], "NumPy": ["numpy"], "Data Analysis": ["data analysis", "data analytics"],
    "Data Visualization": ["data visualization", "data visualisation"], "Excel": ["excel"],
    "Power BI": ["power bi", "powerbi"], "Tableau": ["tableau"], "Statistics": ["statistics"], "Agile": ["agile", "scrum"],
}

STOPWORDS = {"the", "is", "are", "a", "an", "and", "or", "to", "of", "in", "for", "with", "on", "by", "this", "that", "good", "strong"}


def count_term(text: str, phrase: str) -> int:
    return len(re.findall(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text))


def preprocess(text: str) -> str:
    cleaned = "".join(c if c.isalpha() or c.isspace() else " " for c in text.lower())
    return " ".join(w for w in cleaned.split() if w not in STOPWORDS and len(w) > 1)


def has_phone(text: str) -> bool:
    for m in re.finditer(r"\+?\d[\d\s().\-]{8,}\d", text):
        if 10 <= len(re.sub(r"\D", "", m.group())) <= 13:   # ignores year ranges like 2021 - 2024
            return True
    return False


def integrity_score(text: str) -> Tuple[int, List[str]]:
    lower = text.lower()
    score, notes = 0, []
    if EMAIL_RE.search(text):
        score += 20; notes.append("Email present")
    else:
        notes.append("Email missing")
    if has_phone(text):
        score += 20; notes.append("Phone present")
    else:
        notes.append("Phone missing")
    found = [s.title() for s in ("education", "skills", "projects", "experience") if s in lower]
    score += len(found) * 10
    notes.append("Sections found: " + ", ".join(found) if found else "Important sections missing")
    words = len(text.split())
    if words > 40:
        score += 20; notes.append("Detailed content")
    else:
        notes.append("Content too short")
    stuffed = [label for label, alts in SKILLS.items()
               if (c := sum(count_term(lower, a) for a in alts)) >= 8 and words and c / words > 0.04]
    if stuffed:
        score -= 15
        notes.append("Possible keyword stuffing: " + ", ".join(stuffed))
    return max(0, min(score, 100)), notes


def skills_in(text: str) -> List[str]:
    low = text.lower()
    return [label for label, alts in SKILLS.items() if any(count_term(low, a) for a in alts)]


def matched_and_missing(jd: str, resume: str) -> Tuple[List[str], List[str]]:
    required, have = skills_in(jd), set(skills_in(resume))
    return [s for s in required if s in have], [s for s in required if s not in have]


def status_for(final: float, integrity: float) -> str:
    if final >= 70 and integrity >= 60:
        return "Shortlisted"
    return "Review Manually" if final >= 45 else "Rejected"


def suggestions_for(missing: List[str], notes: List[str]) -> List[str]:
    out = [f"Consider acquiring {s} skills." for s in missing]
    text = " ".join(notes).lower()
    if "email missing" in text: out.append("Add a professional email address.")
    if "phone missing" in text: out.append("Add a valid phone number.")
    if "too short" in text: out.append("Expand on projects, skills, and experience.")
    if "keyword stuffing" in text: out.append("Avoid repeating the same keyword; describe real projects instead.")
    return out or ["Resume is robust and well-structured."]


def screen(jd_text: str, resume_text: str) -> dict:
    """Score one resume against one job description."""
    jd_p, res_p = preprocess(jd_text), preprocess(resume_text)
    if not res_p.strip():
        raise ValueError("no readable text")
    vecs = TfidfVectorizer().fit_transform([jd_p, res_p])
    job = round(float(cosine_similarity(vecs[0:1], vecs[1:2])[0][0]) * 100, 2)
    integ, notes = integrity_score(resume_text)
    matched, missing = matched_and_missing(jd_text, resume_text)
    final = round(JOB_MATCH_WEIGHT * job + INTEGRITY_WEIGHT * integ, 2)
    status = status_for(final, integ)
    total = len(matched) + len(missing)
    skill_txt = f"Matched {len(matched)} of {total} required skills. " if total else ""
    verdict = {"Shortlisted": "Strong match.", "Review Manually": "Borderline - needs a human look.",
               "Rejected": "Low match."}[status]
    return {"job_score": job, "integrity_score": integ, "final_score": final, "status": status,
            "matched": matched, "missing": missing, "notes": notes,
            "suggestions": suggestions_for(missing, notes), "explanation": skill_txt + verdict}
