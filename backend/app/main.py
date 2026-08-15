import json
import logging
from datetime import datetime, timedelta
from typing import Any

import stripe
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .emailer import send_email
from .models import Availability, Booking, Delivery, Feedback, InstructorProfile, Notification, PaymentEvent, User
from .security import current_user, hash_password, make_token, require_role, verify_password

logger = logging.getLogger(__name__)
app = FastAPI(title="Raj Instructor API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)

class InstructorRegisterIn(RegisterIn):
    bio: str = Field(min_length=20, max_length=3000)
    teaching_areas: str = Field(min_length=2, max_length=255)
    vehicle: str = Field(min_length=2, max_length=120)
    licence_number: str | None = Field(default=None, max_length=100)
    languages: str = Field(default="English", max_length=255)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class SlotIn(BaseModel):
    starts_at: datetime
    ends_at: datetime

class FeedbackIn(BaseModel):
    lesson_summary: str = Field(min_length=1, max_length=5000)
    agreed_practice: str = Field(min_length=1, max_length=5000)
    further_notes: str = Field(default="", max_length=5000)
    metrics: dict[str, dict[str, Any]]

connections: dict[int, list[WebSocket]] = {}

def serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role}

def booking_view(db: Session, booking: Booking) -> dict[str, Any]:
    slot = db.get(Availability, booking.availability_id)
    instructor = db.get(User, booking.instructor_id)
    student = db.get(User, booking.student_id)
    feedback = db.scalar(select(Feedback).where(Feedback.booking_id == booking.id))
    return {"id": booking.id, "student_id": booking.student_id, "student_name": f"{student.first_name} {student.last_name}", "instructor_id": booking.instructor_id, "instructor_name": f"{instructor.first_name} {instructor.last_name}", "starts_at": slot.starts_at, "ends_at": slot.ends_at, "status": booking.status, "payment_status": booking.payment_status, "amount_cents": booking.amount_cents, "feedback_submitted": bool(feedback)}

def email_safely(to: str, subject: str, body: str) -> bool:
    try:
        send_email(to, subject, body)
        return True
    except Exception:
        logger.exception("Unable to send transactional email to %s", to)
        return False

def notify(db: Session, recipient: User, title: str, body: str, link: str) -> Notification:
    notification = Notification(user_id=recipient.id, title=title, body=body, link=link)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    email_safely(recipient.email, title, f"{body}\n\nOpen Raj Instructor: {settings.frontend_url}{link}")
    return notification

async def push(user_id: int, payload: dict[str, Any]) -> None:
    stale: list[WebSocket] = []
    for websocket in connections.get(user_id, []):
        try:
            await websocket.send_json(payload)
        except Exception:
            stale.append(websocket)
    for websocket in stale:
        connections.get(user_id, []).remove(websocket)

def expire_unpaid_hold(db: Session, slot: Availability) -> None:
    booking = db.scalar(select(Booking).where(Booking.availability_id == slot.id, Booking.status == "pending_payment"))
    if booking and booking.payment_expires_at and booking.payment_expires_at <= datetime.utcnow():
        booking.status = "cancelled"
        booking.payment_status = "expired"
        slot.is_booked = False
        db.commit()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/auth/register")
def register_student(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    learner = User(email=data.email.lower(), hashed_password=hash_password(data.password), first_name=data.first_name, last_name=data.last_name, phone=data.phone, role="student")
    db.add(learner)
    db.commit()
    db.refresh(learner)
    email_safely(learner.email, "Welcome to Raj Instructor", f"Hi {learner.first_name},\n\nYour learner account is ready. Browse instructors, choose a time that works for you, and book your next driving lesson when you are ready.")
    return {"access_token": make_token(learner), "token_type": "bearer", "user": serialize_user(learner)}

@app.post("/auth/register/instructor")
def register_instructor(data: InstructorRegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    instructor = User(email=data.email.lower(), hashed_password=hash_password(data.password), first_name=data.first_name, last_name=data.last_name, phone=data.phone, role="instructor")
    db.add(instructor)
    db.flush()
    db.add(InstructorProfile(user_id=instructor.id, bio=data.bio, teaching_areas=data.teaching_areas, vehicle=data.vehicle, licence_number=data.licence_number, languages=data.languages))
    db.commit()
    db.refresh(instructor)
    email_safely(instructor.email, "Your Raj Instructor account is ready", f"Hi {instructor.first_name},\n\nYour instructor profile is ready. Add your availability to start accepting learner bookings.")
    return {"access_token": make_token(instructor), "token_type": "bearer", "user": serialize_user(instructor)}

@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    account = db.scalar(select(User).where(User.email == data.email.lower()))
    if not account or not verify_password(data.password, account.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": make_token(account), "token_type": "bearer", "user": serialize_user(account)}

@app.get("/me")
def me(account: User = Depends(current_user)):
    return serialize_user(account)

@app.get("/instructors")
def instructors(db: Session = Depends(get_db)):
    rows = db.execute(select(InstructorProfile, User).join(User, InstructorProfile.user_id == User.id).where(InstructorProfile.is_accepting_bookings.is_(True))).all()
    return [{"id": user.id, "name": f"{user.first_name} {user.last_name}", "bio": profile.bio, "expertise": profile.expertise, "services": profile.services, "vehicle": profile.vehicle, "teaching_areas": profile.teaching_areas, "languages": profile.languages, "image_url": profile.image_url, "lesson_price_cents": profile.lesson_price_cents} for profile, user in rows]

@app.get("/availability")
def availability(instructor_id: int | None = None, db: Session = Depends(get_db)):
    query = select(Availability).where(Availability.starts_at >= datetime.utcnow() - timedelta(hours=1))
    if instructor_id:
        query = query.where(Availability.instructor_id == instructor_id)
    result = []
    for slot in db.scalars(query.order_by(Availability.starts_at)).all():
        if slot.is_booked:
            expire_unpaid_hold(db, slot)
        if not slot.is_booked:
            result.append({"id": slot.id, "instructor_id": slot.instructor_id, "starts_at": slot.starts_at, "ends_at": slot.ends_at})
    return result

@app.get("/instructor/availability")
def own_availability(db: Session = Depends(get_db), account: User = Depends(require_role("instructor", "admin"))):
    return [{"id": slot.id, "starts_at": slot.starts_at, "ends_at": slot.ends_at, "is_booked": slot.is_booked} for slot in db.scalars(select(Availability).where(Availability.instructor_id == account.id).order_by(Availability.starts_at)).all()]

@app.post("/instructor/availability")
def add_slot(data: SlotIn, db: Session = Depends(get_db), account: User = Depends(require_role("instructor", "admin"))):
    if data.starts_at < datetime.utcnow() or data.ends_at <= data.starts_at or data.ends_at - data.starts_at > timedelta(hours=4):
        raise HTTPException(400, "Choose a future availability period of up to four hours")
    slot = Availability(instructor_id=account.id, starts_at=data.starts_at, ends_at=data.ends_at)
    db.add(slot)
    try:
        db.commit()
        db.refresh(slot)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This availability slot already exists")
    return {"id": slot.id, "starts_at": slot.starts_at, "ends_at": slot.ends_at}

@app.delete("/instructor/availability/{slot_id}")
def remove_slot(slot_id: int, db: Session = Depends(get_db), account: User = Depends(require_role("instructor", "admin"))):
    slot = db.get(Availability, slot_id)
    if not slot or slot.instructor_id != account.id:
        raise HTTPException(404, "Availability slot not found")
    if slot.is_booked:
        raise HTTPException(409, "A booked slot cannot be removed")
    db.delete(slot)
    db.commit()
    return {"ok": True}

@app.post("/bookings/{slot_id}")
def create_booking(slot_id: int, db: Session = Depends(get_db), account: User = Depends(require_role("student"))):
    slot = db.scalar(select(Availability).where(Availability.id == slot_id).with_for_update())
    if not slot:
        raise HTTPException(404, "Availability slot not found")
    expire_unpaid_hold(db, slot)
    if slot.is_booked or slot.starts_at <= datetime.utcnow():
        raise HTTPException(409, "This time is no longer available")
    profile = db.scalar(select(InstructorProfile).where(InstructorProfile.user_id == slot.instructor_id, InstructorProfile.is_accepting_bookings.is_(True)))
    if not profile:
        raise HTTPException(409, "This instructor is not accepting bookings")
    slot.is_booked = True
    booking = Booking(student_id=account.id, instructor_id=slot.instructor_id, availability_id=slot.id, amount_cents=profile.lesson_price_cents, payment_expires_at=datetime.utcnow() + timedelta(minutes=settings.booking_hold_minutes))
    db.add(booking)
    db.commit()
    db.refresh(booking)
    if settings.payments_mode == "demo":
        booking.payment_status = "paid"
        booking.status = "confirmed"
        booking.payment_expires_at = None
        db.commit()
        notify(db, account, "Lesson booked", "Your lesson is confirmed. Your feedback report will appear after the lesson.", f"/feedback?booking={booking.id}")
        return {"booking_id": booking.id, "checkout_url": f"{settings.frontend_url}/bookings?booked={booking.id}", "mode": "demo"}
    if settings.payments_mode != "stripe" or not settings.stripe_secret_key:
        slot.is_booked = False
        db.delete(booking)
        db.commit()
        raise HTTPException(503, "Payments are temporarily unavailable")
    stripe.api_key = settings.stripe_secret_key
    try:
        checkout = stripe.checkout.Session.create(mode="payment", success_url=f"{settings.frontend_url}/bookings?payment=success&session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{settings.frontend_url}/bookings?payment=cancelled&booking={booking.id}", client_reference_id=str(booking.id), metadata={"booking_id": str(booking.id)}, line_items=[{"price_data": {"currency": "nzd", "product_data": {"name": "Raj Instructor driving lesson"}, "unit_amount": booking.amount_cents}, "quantity": 1}])
    except Exception:
        logger.exception("Stripe checkout creation failed")
        slot.is_booked = False
        db.delete(booking)
        db.commit()
        raise HTTPException(503, "Could not start secure checkout. Please try again.")
    booking.stripe_session_id = checkout.id
    db.commit()
    return {"booking_id": booking.id, "checkout_url": checkout.url, "mode": "stripe"}

@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, db: Session = Depends(get_db), account: User = Depends(current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or (account.role == "student" and booking.student_id != account.id) or (account.role == "instructor" and booking.instructor_id != account.id):
        raise HTTPException(404, "Booking not found")
    if booking.status != "pending_payment":
        raise HTTPException(409, "Only unpaid bookings can be cancelled online")
    booking.status = "cancelled"
    booking.payment_status = "cancelled"
    db.get(Availability, booking.availability_id).is_booked = False
    db.commit()
    return {"ok": True}

@app.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Stripe webhook is not configured")
    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(400, "Invalid Stripe webhook signature")
    if db.scalar(select(PaymentEvent).where(PaymentEvent.provider_event_id == event["id"])):
        return {"received": True, "duplicate": True}
    db.add(PaymentEvent(provider_event_id=event["id"], event_type=event["type"]))
    if event["type"] == "checkout.session.completed":
        checkout = event["data"]["object"]
        booking_id = int(checkout["metadata"]["booking_id"])
        booking = db.get(Booking, booking_id)
        if booking and booking.status == "pending_payment":
            booking.payment_status = "paid"
            booking.status = "confirmed"
            booking.payment_reference = checkout.get("payment_intent")
            booking.payment_expires_at = None
            db.commit()
            student = db.get(User, booking.student_id)
            notice = notify(db, student, "Payment received", "Your driving lesson is confirmed. We have emailed your booking details.", f"/bookings?booking={booking.id}")
            await push(student.id, {"type": "notification", "id": notice.id, "title": notice.title, "body": notice.body, "link": notice.link})
            return {"received": True}
    db.commit()
    return {"received": True}

@app.get("/bookings")
def bookings(db: Session = Depends(get_db), account: User = Depends(current_user)):
    query = select(Booking)
    if account.role == "student": query = query.where(Booking.student_id == account.id)
    elif account.role == "instructor": query = query.where(Booking.instructor_id == account.id)
    return [booking_view(db, booking) for booking in db.scalars(query.order_by(Booking.created_at.desc())).all()]

@app.post("/instructor/bookings/{booking_id}/complete")
def complete_booking(booking_id: int, db: Session = Depends(get_db), account: User = Depends(require_role("instructor", "admin"))):
    booking = db.get(Booking, booking_id)
    if not booking or (account.role == "instructor" and booking.instructor_id != account.id):
        raise HTTPException(404, "Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(409, "Only confirmed lessons can be completed")
    booking.status = "completed"
    db.commit()
    return {"ok": True}

@app.post("/instructor/bookings/{booking_id}/feedback")
async def submit_feedback(booking_id: int, data: FeedbackIn, db: Session = Depends(get_db), account: User = Depends(require_role("instructor", "admin"))):
    booking = db.get(Booking, booking_id)
    if not booking or (account.role == "instructor" and booking.instructor_id != account.id):
        raise HTTPException(404, "Booking not found")
    if booking.status not in {"confirmed", "completed"}:
        raise HTTPException(409, "Feedback can only be submitted for a confirmed lesson")
    slot = db.get(Availability, booking.availability_id)
    if slot.ends_at > datetime.utcnow():
        raise HTTPException(409, "Feedback can be submitted after the lesson has ended")
    if db.scalar(select(Feedback).where(Feedback.booking_id == booking_id)):
        raise HTTPException(409, "Feedback has already been submitted")
    feedback = Feedback(booking_id=booking.id, student_id=booking.student_id, instructor_id=booking.instructor_id, lesson_summary=data.lesson_summary, agreed_practice=data.agreed_practice, further_notes=data.further_notes, metrics_json=json.dumps(data.metrics))
    booking.status = "completed"
    db.add(feedback)
    db.commit()
    student = db.get(User, booking.student_id)
    notice = notify(db, student, "New lesson feedback", "Your instructor has submitted your driving lesson feedback report.", f"/feedback?booking={booking.id}")
    await push(student.id, {"type": "notification", "id": notice.id, "title": notice.title, "body": notice.body, "link": notice.link})
    return {"id": feedback.id}

@app.get("/feedback")
def feedback(db: Session = Depends(get_db), account: User = Depends(current_user)):
    query = select(Booking)
    if account.role == "student": query = query.where(Booking.student_id == account.id)
    elif account.role == "instructor": query = query.where(Booking.instructor_id == account.id)
    rows = []
    for booking in db.scalars(query.order_by(Booking.created_at.asc())).all():
        view = booking_view(db, booking)
        report = db.scalar(select(Feedback).where(Feedback.booking_id == booking.id))
        rows.append({"booking_id": booking.id, "starts_at": view["starts_at"], "instructor_name": view["instructor_name"], "student_name": view["student_name"], "status": "submitted" if report else "pending", "lesson_summary": report.lesson_summary if report else "Feedback will appear here after the lesson.", "agreed_practice": report.agreed_practice if report else "", "further_notes": report.further_notes if report else "", "metrics": json.loads(report.metrics_json) if report else {}})
    return rows

@app.get("/notifications")
def notifications(db: Session = Depends(get_db), account: User = Depends(current_user)):
    return [{"id": item.id, "title": item.title, "body": item.body, "link": item.link, "is_read": item.is_read, "created_at": item.created_at} for item in db.scalars(select(Notification).where(Notification.user_id == account.id).order_by(Notification.created_at.desc())).all()]

@app.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), account: User = Depends(current_user)):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != account.id:
        raise HTTPException(404, "Notification not found")
    notification.is_read = True
    db.commit()
    return {"ok": True}

@app.post("/internal/reminders/run")
def send_reminders(request: Request, db: Session = Depends(get_db)):
    provided_secret = request.headers.get("x-reminder-secret") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if not settings.reminder_secret or provided_secret != settings.reminder_secret:
        raise HTTPException(401, "Invalid reminder secret")
    now = datetime.utcnow()
    student_until = now + timedelta(hours=settings.reminder_hours_before)
    instructor_until = now - timedelta(minutes=settings.feedback_reminder_minutes_after)
    sent = 0
    for booking in db.scalars(select(Booking).where(Booking.status == "confirmed")).all():
        slot = db.get(Availability, booking.availability_id)
        if now <= slot.starts_at <= student_until:
            exists = db.scalar(select(Delivery).where(Delivery.booking_id == booking.id, Delivery.user_id == booking.student_id, Delivery.kind == "student_lesson_reminder"))
            if not exists:
                student = db.get(User, booking.student_id)
                if email_safely(student.email, "Your driving lesson is coming up", f"Your lesson starts at {slot.starts_at.isoformat()} UTC. Open Raj Instructor for your booking details."):
                    db.add(Delivery(booking_id=booking.id, user_id=student.id, kind="student_lesson_reminder")); sent += 1
        if slot.ends_at <= instructor_until:
            exists = db.scalar(select(Delivery).where(Delivery.booking_id == booking.id, Delivery.user_id == booking.instructor_id, Delivery.kind == "instructor_feedback_reminder"))
            feedback_exists = db.scalar(select(Feedback).where(Feedback.booking_id == booking.id))
            if not exists and not feedback_exists:
                instructor = db.get(User, booking.instructor_id)
                if email_safely(instructor.email, "Lesson feedback is ready to complete", f"Please complete the feedback report for the lesson that ended at {slot.ends_at.isoformat()} UTC."):
                    db.add(Delivery(booking_id=booking.id, user_id=instructor.id, kind="instructor_feedback_reminder")); sent += 1
    db.commit()
    return {"sent": sent}

@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket: WebSocket, user_id: int, token: str):
    from jose import jwt
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if int(payload.get("sub")) != user_id: raise ValueError()
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    connections.setdefault(user_id, []).append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connections.get(user_id, []): connections[user_id].remove(websocket)

@app.post("/dev/seed")
def seed(db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == "instructor@example.com")): return {"message": "already seeded"}
    instructor = User(email="instructor@example.com", hashed_password=hash_password("Password123!"), first_name="Raj", last_name="Chandra", role="instructor")
    student = User(email="student@example.com", hashed_password=hash_password("Password123!"), first_name="Demo", last_name="Student", role="student")
    db.add_all([instructor, student]); db.flush()
    db.add(InstructorProfile(user_id=instructor.id, bio="A calm, patient instructor focused on safe habits, confidence and practical test preparation.", expertise="Learner driving, restricted and full test preparation, confidence building", services="One-hour lessons, mock tests, urban driving coaching", vehicle="Automatic dual-control training vehicle", teaching_areas="Auckland Central and surrounding suburbs", languages="English", lesson_price_cents=9000))
    base = (datetime.utcnow() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    for day in range(7):
        for hour in (9, 11, 14, 16):
            starts_at = (base + timedelta(days=day)).replace(hour=hour)
            db.add(Availability(instructor_id=instructor.id, starts_at=starts_at, ends_at=starts_at + timedelta(hours=1)))
    db.commit()
    return {"message": "seeded", "student": "student@example.com / Password123!", "instructor": "instructor@example.com / Password123!"}
