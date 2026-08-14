from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="student")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class InstructorProfile(Base):
    __tablename__ = "instructor_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    expertise: Mapped[str] = mapped_column(Text, default="Learner lessons, test preparation")
    services: Mapped[str] = mapped_column(Text, default="1-hour driving lessons")
    vehicle: Mapped[str] = mapped_column(String(120), default="Automatic training vehicle")
    teaching_areas: Mapped[str] = mapped_column(String(255), default="Auckland")
    languages: Mapped[str] = mapped_column(String(255), default="English")
    image_url: Mapped[str] = mapped_column(String(500), default="/instructor-placeholder.svg")
    lesson_price_cents: Mapped[int] = mapped_column(Integer, default=9000)
    licence_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_accepting_bookings: Mapped[bool] = mapped_column(Boolean, default=True)
    user = relationship("User")

class Availability(Base):
    __tablename__ = "availability"
    id: Mapped[int] = mapped_column(primary_key=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("instructor_id", "starts_at", name="uq_instructor_slot"),)

class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    availability_id: Mapped[int] = mapped_column(ForeignKey("availability.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_payment")
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid")
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=9000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_summary: Mapped[str] = mapped_column(Text, default="")
    agreed_practice: Mapped[str] = mapped_column(Text, default="")
    further_notes: Mapped[str] = mapped_column(Text, default="")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(500), default="/dashboard")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("booking_id", "user_id", "kind", name="uq_delivery_once"),)
