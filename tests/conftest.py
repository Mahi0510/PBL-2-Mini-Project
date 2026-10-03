import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="titan-test-")
os.environ.update({
    "DATABASE_PATH": os.path.join(_tmp, "test.db"), "UPLOAD_DIR": os.path.join(_tmp, "uploads"),
    "ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "testpass", "SMTP_USER": "", "SMTP_PASSWORD": "",
    "RETENTION_DAYS": "0", "COMPANY_NAME": "TestCo",
})

import pymupdf  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 60), text)
    data = doc.tobytes()
    doc.close()
    return data


GOOD_RESUME = ("Jane Doe jane@example.com +91 98765 43210 Education: B.Tech 2021 - 2025 "
               "Skills: Python, FastAPI, scikit-learn, Git, NLP Projects: machine learning pipeline using natural language "
               "processing Experience: intern building FastAPI services with Git workflows for hiring teams")


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        with main.db() as conn:
            for t in ("screening_results", "system_logs", "communications", "sessions"):
                conn.execute(f"DELETE FROM {t}")
        main.login_limiter.clear(); main.apply_limiter.clear()
        yield c


@pytest.fixture()
def admin(client):
    assert client.post("/login", data={"username": "admin", "password": "testpass"}).status_code == 200
    return client


def apply(client, name="Jane Doe", email="jane@example.com", role="Python Developer", consent="true", pdf=None, filename="cv.pdf"):
    pdf = make_pdf(GOOD_RESUME) if pdf is None else pdf
    return client.post("/apply", data={"name": name, "email": email, "role": role, "consent": consent},
                       files=[("resumes", (filename, pdf, "application/pdf"))])
