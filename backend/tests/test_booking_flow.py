from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Availability


def headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_instructor_and_student_booking_feedback_flow():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    instructor = client.post("/auth/register/instructor", json={"email": "raj@example.com", "password": "Password123!", "first_name": "Raj", "last_name": "Chandra", "bio": "Patient coaching for learner drivers building safe skills.", "teaching_areas": "Auckland", "vehicle": "Automatic dual-control vehicle", "languages": "English"})
    assert instructor.status_code == 200
    instructor_token = instructor.json()["access_token"]
    learner = client.post("/auth/register", json={"email": "learner@example.com", "password": "Password123!", "first_name": "Learner", "last_name": "One"})
    assert learner.status_code == 200
    learner_token = learner.json()["access_token"]

    starts = datetime.utcnow() + timedelta(days=2)
    slot = client.post("/instructor/availability", headers=headers(instructor_token), json={"starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat()})
    assert slot.status_code == 200
    booked = client.post(f"/bookings/{slot.json()['id']}", headers=headers(learner_token))
    assert booked.status_code == 200
    assert booked.json()["mode"] == "demo"
    assert client.get("/bookings", headers=headers(learner_token)).json()[0]["status"] == "confirmed"

    db = SessionLocal()
    saved_slot = db.get(Availability, slot.json()["id"])
    saved_slot.starts_at = datetime.utcnow() - timedelta(hours=2)
    saved_slot.ends_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    db.close()
    feedback = client.post(f"/instructor/bookings/{booked.json()['booking_id']}/feedback", headers=headers(instructor_token), json={"lesson_summary": "Good progress with observation and steering.", "agreed_practice": "Practise mirror checks before each manoeuvre.", "further_notes": "Keep building confidence.", "metrics": {"Mirrors and scanning": {"rating": 6, "comment": "Good improvement"}}})
    assert feedback.status_code == 200
    report = client.get("/feedback", headers=headers(learner_token)).json()
    assert report[0]["status"] == "submitted"
    assert report[0]["metrics"]["Mirrors and scanning"]["rating"] == 6
