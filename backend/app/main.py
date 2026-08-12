import json
from datetime import datetime, timedelta
from typing import Any
import stripe
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from .database import Base, engine, get_db, SessionLocal
from .models import User, InstructorProfile, Availability, Booking, Feedback, Notification
from .security import hash_password, verify_password, make_token, current_user, require_role
from .config import settings
from .emailer import send_email

app = FastAPI(title="DriveBook API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)

class RegisterIn(BaseModel):
    email: EmailStr; password: str = Field(min_length=8); first_name: str; last_name: str; phone: str | None = None
class LoginIn(BaseModel): email: EmailStr; password: str
class SlotIn(BaseModel): starts_at: datetime; ends_at: datetime
class FeedbackIn(BaseModel): lesson_summary: str; agreed_practice: str; further_notes: str = ""; metrics: dict[str, dict[str, Any]]

connections: dict[int, list[WebSocket]] = {}
async def push(user_id: int, payload: dict):
    dead=[]
    for ws in connections.get(user_id, []):
        try: await ws.send_json(payload)
        except Exception: dead.append(ws)
    for ws in dead:
        if ws in connections.get(user_id, []): connections[user_id].remove(ws)

def notify(db: Session, user: User, title: str, body: str, link: str):
    n=Notification(user_id=user.id,title=title,body=body,link=link); db.add(n); db.commit(); db.refresh(n)
    send_email(user.email,title,f"{body}\n\nOpen: {settings.frontend_url}{link}")
    return n

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/auth/register")
def register(data: RegisterIn, db: Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==data.email)):
        raise HTTPException(409,"Email already registered")
    u=User(email=data.email,hashed_password=hash_password(data.password),first_name=data.first_name,last_name=data.last_name,phone=data.phone,role="student")
    db.add(u); db.commit(); db.refresh(u)
    return {"access_token":make_token(u),"token_type":"bearer","user":{"id":u.id,"email":u.email,"first_name":u.first_name,"last_name":u.last_name,"role":u.role}}

@app.post("/auth/login")
def login(data: LoginIn, db: Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email))
    if not u or not verify_password(data.password,u.hashed_password): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":make_token(u),"token_type":"bearer","user":{"id":u.id,"email":u.email,"first_name":u.first_name,"last_name":u.last_name,"role":u.role}}

@app.get("/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"email":u.email,"first_name":u.first_name,"last_name":u.last_name,"role":u.role}

@app.get("/instructors")
def instructors(db:Session=Depends(get_db)):
    rows=db.execute(select(InstructorProfile,User).join(User,InstructorProfile.user_id==User.id)).all()
    return [{"id":u.id,"name":f"{u.first_name} {u.last_name}","bio":p.bio,"expertise":p.expertise,"services":p.services,"vehicle":p.vehicle,"teaching_areas":p.teaching_areas,"languages":p.languages,"image_url":p.image_url,"lesson_price_cents":p.lesson_price_cents} for p,u in rows]

@app.get("/availability")
def availability(instructor_id:int|None=None, db:Session=Depends(get_db)):
    q=select(Availability).where(Availability.starts_at>=datetime.utcnow()-timedelta(hours=1), Availability.is_booked==False)
    if instructor_id: q=q.where(Availability.instructor_id==instructor_id)
    slots=db.scalars(q.order_by(Availability.starts_at)).all()
    return [{"id":s.id,"instructor_id":s.instructor_id,"starts_at":s.starts_at,"ends_at":s.ends_at} for s in slots]

@app.post("/instructor/availability")
def add_slot(data:SlotIn, db:Session=Depends(get_db), u:User=Depends(require_role("instructor","admin"))):
    if data.ends_at<=data.starts_at: raise HTTPException(400,"End must be after start")
    s=Availability(instructor_id=u.id,starts_at=data.starts_at,ends_at=data.ends_at); db.add(s)
    try: db.commit(); db.refresh(s)
    except Exception: db.rollback(); raise HTTPException(409,"This availability slot already exists")
    return {"id":s.id,"starts_at":s.starts_at,"ends_at":s.ends_at}

@app.post("/bookings/{slot_id}")
def create_booking(slot_id:int, db:Session=Depends(get_db), u:User=Depends(require_role("student"))):
    slot=db.get(Availability,slot_id)
    if not slot or slot.is_booked: raise HTTPException(409,"Slot is no longer available")
    prof=db.scalar(select(InstructorProfile).where(InstructorProfile.user_id==slot.instructor_id))
    amount=prof.lesson_price_cents if prof else 9000
    slot.is_booked=True
    b=Booking(student_id=u.id,instructor_id=slot.instructor_id,availability_id=slot.id,amount_cents=amount)
    db.add(b); db.commit(); db.refresh(b)
    if settings.payments_mode=="demo":
        b.payment_status="paid"; b.status="confirmed"; db.commit()
        notify(db,u,"Lesson booked","Your lesson is confirmed. A feedback page has been reserved for this lesson.",f"/feedback?booking={b.id}")
        return {"booking_id":b.id,"checkout_url":f"{settings.frontend_url}/bookings?booked={b.id}","mode":"demo"}
    if not settings.stripe_secret_key: raise HTTPException(500,"Stripe is not configured")
    stripe.api_key=settings.stripe_secret_key
    session=stripe.checkout.Session.create(mode="payment",success_url=f"{settings.frontend_url}/bookings?payment=success&session_id={{CHECKOUT_SESSION_ID}}",cancel_url=f"{settings.frontend_url}/dashboard?payment=cancelled",client_reference_id=str(b.id),metadata={"booking_id":str(b.id)},line_items=[{"price_data":{"currency":"nzd","product_data":{"name":"Driving lesson"},"unit_amount":amount},"quantity":1}])
    b.stripe_session_id=session.id; db.commit()
    return {"booking_id":b.id,"checkout_url":session.url,"mode":"stripe"}

@app.post("/payments/stripe/webhook")
async def stripe_webhook(request:Request, db:Session=Depends(get_db)):
    payload=await request.body(); sig=request.headers.get("stripe-signature","")
    try:
        event=stripe.Webhook.construct_event(payload,sig,settings.stripe_webhook_secret)
    except Exception as e: raise HTTPException(400,str(e))
    if event["type"]=="checkout.session.completed":
        session=event["data"]["object"]; bid=int(session["metadata"]["booking_id"])
        b=db.get(Booking,bid)
        if b:
            b.payment_status="paid"; b.status="confirmed"; db.commit(); student=db.get(User,b.student_id)
            notify(db,student,"Payment received","Your driving lesson is confirmed.",f"/bookings?booking={b.id}")
            await push(student.id,{"type":"notification","title":"Payment received","link":f"/bookings?booking={b.id}"})
    return {"received":True}

@app.get("/bookings")
def bookings(db:Session=Depends(get_db), u:User=Depends(current_user)):
    if u.role=="student": q=select(Booking).where(Booking.student_id==u.id)
    elif u.role=="instructor": q=select(Booking).where(Booking.instructor_id==u.id)
    else: q=select(Booking)
    out=[]
    for b in db.scalars(q.order_by(Booking.created_at.desc())).all():
        s=db.get(Availability,b.availability_id); inst=db.get(User,b.instructor_id); student=db.get(User,b.student_id)
        fb=db.scalar(select(Feedback).where(Feedback.booking_id==b.id))
        out.append({"id":b.id,"student_id":b.student_id,"student_name":f"{student.first_name} {student.last_name}","instructor_id":b.instructor_id,"instructor_name":f"{inst.first_name} {inst.last_name}","starts_at":s.starts_at,"ends_at":s.ends_at,"status":b.status,"payment_status":b.payment_status,"amount_cents":b.amount_cents,"feedback_submitted":bool(fb)})
    return out

@app.post("/instructor/bookings/{booking_id}/complete")
def complete(booking_id:int, db:Session=Depends(get_db), u:User=Depends(require_role("instructor","admin"))):
    b=db.get(Booking,booking_id)
    if not b or (u.role=="instructor" and b.instructor_id!=u.id): raise HTTPException(404,"Booking not found")
    b.status="completed"; db.commit(); return {"ok":True}

@app.post("/instructor/bookings/{booking_id}/feedback")
async def submit_feedback(booking_id:int,data:FeedbackIn,db:Session=Depends(get_db),u:User=Depends(require_role("instructor","admin"))):
    b=db.get(Booking,booking_id)
    if not b or (u.role=="instructor" and b.instructor_id!=u.id): raise HTTPException(404,"Booking not found")
    if db.scalar(select(Feedback).where(Feedback.booking_id==booking_id)): raise HTTPException(409,"Feedback already submitted")
    f=Feedback(booking_id=b.id,student_id=b.student_id,instructor_id=b.instructor_id,lesson_summary=data.lesson_summary,agreed_practice=data.agreed_practice,further_notes=data.further_notes,metrics_json=json.dumps(data.metrics))
    b.status="completed"; db.add(f); db.commit(); db.refresh(f)
    student=db.get(User,b.student_id); n=notify(db,student,"New lesson feedback","Your instructor has submitted feedback for your latest lesson.",f"/feedback?booking={b.id}")
    await push(student.id,{"type":"notification","id":n.id,"title":n.title,"body":n.body,"link":n.link})
    return {"id":f.id}

@app.get("/feedback")
def feedback(db:Session=Depends(get_db),u:User=Depends(current_user)):
    if u.role=="student": q=select(Booking).where(Booking.student_id==u.id)
    elif u.role=="instructor": q=select(Booking).where(Booking.instructor_id==u.id)
    else: q=select(Booking)
    rows=[]
    for b in db.scalars(q.order_by(Booking.created_at.asc())).all():
        s=db.get(Availability,b.availability_id); inst=db.get(User,b.instructor_id); student=db.get(User,b.student_id); f=db.scalar(select(Feedback).where(Feedback.booking_id==b.id))
        rows.append({"booking_id":b.id,"starts_at":s.starts_at,"instructor_name":f"{inst.first_name} {inst.last_name}","student_name":f"{student.first_name} {student.last_name}","status":"submitted" if f else "pending","lesson_summary":f.lesson_summary if f else "Feedback will appear here after the lesson.","agreed_practice":f.agreed_practice if f else "","further_notes":f.further_notes if f else "","metrics":json.loads(f.metrics_json) if f else {}})
    return rows

@app.get("/notifications")
def notifications(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.scalars(select(Notification).where(Notification.user_id==u.id).order_by(Notification.created_at.desc())).all()
    return [{"id":n.id,"title":n.title,"body":n.body,"link":n.link,"is_read":n.is_read,"created_at":n.created_at} for n in rows]

@app.post("/notifications/{notification_id}/read")
def mark_read(notification_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    n=db.get(Notification,notification_id)
    if not n or n.user_id!=u.id: raise HTTPException(404,"Notification not found")
    n.is_read=True; db.commit(); return {"ok":True}

@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket:WebSocket,user_id:int,token:str):
    # lightweight token validation via dependency logic is awkward in websockets; decode directly
    from jose import jwt
    try:
        payload=jwt.decode(token,settings.jwt_secret,algorithms=["HS256"])
        if int(payload.get("sub"))!=user_id: raise ValueError()
    except Exception:
        await websocket.close(code=4401); return
    await websocket.accept(); connections.setdefault(user_id,[]).append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connections.get(user_id,[]): connections[user_id].remove(websocket)

@app.post("/dev/seed")
def seed(db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email=="instructor@example.com")): return {"message":"already seeded"}
    instructor=User(email="instructor@example.com",hashed_password=hash_password("Password123!"),first_name="Alex",last_name="Morgan",role="instructor")
    student=User(email="student@example.com",hashed_password=hash_password("Password123!"),first_name="Demo",last_name="Student",role="student")
    db.add_all([instructor,student]); db.commit(); db.refresh(instructor)
    prof=InstructorProfile(user_id=instructor.id,bio="A calm, patient instructor focused on safe habits, confidence and practical test preparation.",expertise="Learner driving, restricted/full test preparation, confidence building",services="1-hour lessons, mock tests, urban driving coaching",vehicle="Automatic dual-control training vehicle",teaching_areas="Auckland Central and surrounding suburbs",languages="English",lesson_price_cents=9000)
    db.add(prof)
    base=(datetime.utcnow()+timedelta(days=1)).replace(minute=0,second=0,microsecond=0)
    for d in range(7):
        for h in (9,11,14,16):
            st=(base+timedelta(days=d)).replace(hour=h); db.add(Availability(instructor_id=instructor.id,starts_at=st,ends_at=st+timedelta(hours=1)))
    db.commit(); return {"message":"seeded","student":"student@example.com / Password123!","instructor":"instructor@example.com / Password123!"}
