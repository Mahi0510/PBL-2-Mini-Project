from datetime import datetime, timedelta

from tests.conftest import apply, make_pdf


def test_hr_endpoints_require_login(client):
    for url in ("/api/pipeline", "/api/logs", "/api/comms", "/api/roles/all", "/preview/x.pdf"):
        assert client.get(url).status_code == 401
    assert client.post("/update-decision", data={"candidate_id": 1, "decision": "Hold"}).status_code == 401
    assert client.delete("/api/candidates/1").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/login", data={"username": "admin", "password": "testpass"}).status_code == 429


def test_logout_invalidates_session(admin):
    assert admin.get("/api/me").status_code == 200
    admin.post("/logout")
    assert admin.get("/api/me").status_code == 401


def test_public_pages_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/careers").status_code == 200
    assert "TestCo" == client.get("/api/public-config").json()["company"]
    assert "Python Developer" in client.get("/api/roles").json()["roles"]
    r = client.get("/")
    assert r.headers["x-frame-options"] == "DENY" and "content-security-policy" in r.headers


def test_apply_requires_consent_and_valid_input(client):
    assert apply(client, consent="false").status_code == 400
    assert apply(client, email="not-an-email").status_code == 400
    assert apply(client, role="Astronaut").status_code == 400
    assert apply(client, pdf=b"not a pdf").status_code == 400
    assert apply(client, filename="cv.docx").status_code == 400


def test_full_flow_apply_review_decide_delete(admin):
    r = apply(admin, name="<script>alert(1)</script>")
    assert r.status_code == 200 and r.json()["processed"] == 1
    cand = admin.get("/api/pipeline").json()["candidates"][0]
    assert cand["status"] in ("Shortlisted", "Review Manually", "Rejected") and cand["hr_decision"] == "Pending"
    assert admin.get(f"/preview/{cand['resume_filename']}").status_code == 200
    assert admin.get("/preview/..%2F.env").status_code == 404

    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    base = {"candidate_id": cand["id"], "decision": "Interview Scheduled"}
    assert admin.post("/update-decision", data={**base, "time": past}).status_code == 400
    assert admin.post("/update-decision", data={**base, "time": future}).status_code == 200
    assert admin.post("/update-decision", data={"candidate_id": 9999, "decision": "Hold"}).status_code == 404
    assert admin.get("/api/pipeline").json()["candidates"][0]["hr_decision"].startswith("Interview on")

    assert admin.delete(f"/api/candidates/{cand['id']}").status_code == 200
    assert admin.get("/api/pipeline").json()["candidates"] == []
    assert admin.get(f"/preview/{cand['resume_filename']}").status_code == 404


def test_duplicate_application_blocked(client):
    assert apply(client).status_code == 200
    assert apply(client).status_code == 409


def test_apply_rate_limit(client):
    for i in range(10):
        apply(client, email=f"user{i}@example.com")
    assert apply(client, email="late@example.com").status_code == 429


def test_roles_management(admin, client):
    desc = "Backend engineer with Python, Docker, PostgreSQL and AWS experience building APIs."
    r = admin.post("/api/roles", data={"title": "Backend Engineer", "description": desc})
    assert r.status_code == 200 and "Docker" in r.json()["detected_skills"]
    assert admin.post("/api/roles", data={"title": "Backend Engineer", "description": desc}).status_code == 409
    assert admin.post("/api/roles", data={"title": "X", "description": "too short"}).status_code == 400
    role_id = [x for x in admin.get("/api/roles/all").json()["roles"] if x["title"] == "Backend Engineer"][0]["id"]
    admin.post(f"/api/roles/{role_id}/toggle")
    assert "Backend Engineer" not in admin.get("/api/roles").json()["roles"]
    assert apply(admin, role="Backend Engineer", email="b@example.com").status_code == 400


def test_retention_purge(admin):
    from app import main
    apply(admin)
    with main.db() as c:
        c.execute("UPDATE screening_results SET created_at = '2020-01-01 00:00:00'")
    assert main.purge_old(30) == 1
    assert admin.get("/api/pipeline").json()["candidates"] == []
