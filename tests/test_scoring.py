from app import scoring
from tests.conftest import GOOD_RESUME

JD = "Looking for a Python Developer with Machine Learning, Natural Language Processing, FastAPI, Git and Data Analysis."


def test_skill_detection_uses_whole_words_and_aliases():
    assert "Git" not in scoring.skills_in("digital marketing")
    assert "NLP" in scoring.skills_in("experience in natural language processing")
    assert "Scikit-learn" in scoring.skills_in("used sklearn daily")
    assert "C++" in scoring.skills_in("strong C++ skills")


def test_matched_and_missing():
    matched, missing = scoring.matched_and_missing(JD, GOOD_RESUME)
    assert "Python" in matched and "FastAPI" in matched and "NLP" in matched
    assert missing == ["Data Analysis"]


def test_year_ranges_are_not_phone_numbers():
    assert not scoring.has_phone("Education 2021 - 2025 and 2019 - 2021")
    assert scoring.has_phone("Call +91 98765 43210")


def test_keyword_stuffing_is_penalised():
    stuffed = "python " * 40 + "email a@b.com education skills projects experience"
    score, notes = scoring.integrity_score(stuffed)
    assert any("keyword stuffing" in n.lower() for n in notes)


def test_screen_returns_complete_result():
    r = scoring.screen(JD, GOOD_RESUME)
    assert 0 <= r["final_score"] <= 100 and r["status"] in ("Shortlisted", "Review Manually", "Rejected")
    assert "required skills" in r["explanation"]


def test_unreadable_resume_raises():
    import pytest
    with pytest.raises(ValueError):
        scoring.screen(JD, "   12345 !!! ")
