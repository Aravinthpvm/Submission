from datetime import datetime, timedelta
import logging
import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import (
    MONITORING_API_KEY,
    create_access_token,
    create_monitoring_token,
    hash_password,
    verify_password,
)
from .database import Base, engine, get_db
from .deps import get_current_user, get_monitoring_claims, require_roles
from .models import Attendance, Batch, BatchInvite, BatchStudent, BatchTrainer, Session, User
from .schemas import (
    AttendanceMarkRequest,
    BatchCreateRequest,
    BatchJoinRequest,
    LoginRequest,
    MessageResponse,
    MonitoringTokenRequest,
    SessionCreateRequest,
    SignupRequest,
    TokenResponse,
)

app = FastAPI(title="SkillBridge Attendance API")

logger = logging.getLogger(__name__)


@app.on_event("startup")
def startup_init_db():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        logger.exception("Database initialization failed. Check DATABASE_URL format and network access.")
        raise


@app.post("/auth/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if payload.institution_id is not None:
        institution = db.query(User).filter(User.id == payload.institution_id, User.role == "institution").first()
        if not institution:
            raise HTTPException(status_code=404, detail="Institution not found")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        institution_id=payload.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id, user.role))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(access_token=create_access_token(user.id, user.role))


@app.post("/auth/monitoring-token", response_model=TokenResponse)
def create_monitoring_readonly_token(
    body: MonitoringTokenRequest,
    current_user: User = Depends(require_roles("monitoring_officer")),
):
    if body.key != MONITORING_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid monitoring API key")
    token = create_monitoring_token(current_user.id, current_user.role)
    return TokenResponse(access_token=token)


@app.post("/batches", status_code=201)
def create_batch(
    payload: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("trainer", "institution")),
):
    institution = db.query(User).filter(User.id == payload.institution_id, User.role == "institution").first()
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")

    if current_user.role == "institution" and current_user.id != payload.institution_id:
        raise HTTPException(status_code=403, detail="Institution can create only its own batches")

    batch = Batch(name=payload.name, institution_id=payload.institution_id)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    if current_user.role == "trainer":
        db.add(BatchTrainer(batch_id=batch.id, trainer_id=current_user.id))
        db.commit()

    return {"id": batch.id, "name": batch.name, "institution_id": batch.institution_id}


@app.post("/batches/{batch_id}/invite", status_code=201)
def create_batch_invite(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("trainer")),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    trainer_link = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == batch_id, BatchTrainer.trainer_id == current_user.id)
        .first()
    )
    if not trainer_link:
        raise HTTPException(status_code=403, detail="Trainer is not assigned to this batch")

    token = secrets.token_urlsafe(24)
    invite = BatchInvite(
        batch_id=batch_id,
        token=token,
        created_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {"invite_token": invite.token, "expires_at": invite.expires_at.isoformat()}


@app.post("/batches/join", response_model=MessageResponse)
def join_batch(
    payload: BatchJoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    invite = db.query(BatchInvite).filter(BatchInvite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite token not found")
    if invite.used:
        raise HTTPException(status_code=400, detail="Invite token already used")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite token expired")

    already_joined = (
        db.query(BatchStudent)
        .filter(BatchStudent.batch_id == invite.batch_id, BatchStudent.student_id == current_user.id)
        .first()
    )
    if already_joined:
        raise HTTPException(status_code=400, detail="Student already joined this batch")

    db.add(BatchStudent(batch_id=invite.batch_id, student_id=current_user.id))
    invite.used = True
    db.commit()

    return MessageResponse(message="Joined batch successfully")


@app.post("/sessions", status_code=201)
def create_session(
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("trainer")),
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be later than start_time")

    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    trainer_link = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == payload.batch_id, BatchTrainer.trainer_id == current_user.id)
        .first()
    )
    if not trainer_link:
        raise HTTPException(status_code=403, detail="Trainer is not assigned to this batch")

    session = Session(
        batch_id=payload.batch_id,
        trainer_id=current_user.id,
        title=payload.title,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "title": session.title,
        "batch_id": session.batch_id,
        "trainer_id": session.trainer_id,
    }


@app.post("/attendance/mark", status_code=201)
def mark_attendance(
    payload: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    session = db.query(Session).filter(Session.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    enrollment = (
        db.query(BatchStudent)
        .filter(BatchStudent.batch_id == session.batch_id, BatchStudent.student_id == current_user.id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Student is not enrolled in this session's batch")

    now = datetime.utcnow()
    if session.date != now.date() or not (session.start_time <= now.time() <= session.end_time):
        raise HTTPException(status_code=403, detail="Session is not active")

    record = (
        db.query(Attendance)
        .filter(Attendance.session_id == payload.session_id, Attendance.student_id == current_user.id)
        .first()
    )
    if record:
        record.status = payload.status
        record.marked_at = datetime.utcnow()
    else:
        record = Attendance(
            session_id=payload.session_id,
            student_id=current_user.id,
            status=payload.status,
        )
        db.add(record)

    db.commit()
    return {"id": record.id, "session_id": record.session_id, "status": record.status}


@app.get("/sessions/{session_id}/attendance")
def get_session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("trainer")),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    trainer_link = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == session.batch_id, BatchTrainer.trainer_id == current_user.id)
        .first()
    )
    if not trainer_link and session.trainer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Trainer is not allowed to view this session")

    rows = (
        db.query(Attendance, User)
        .join(User, User.id == Attendance.student_id)
        .filter(Attendance.session_id == session_id)
        .all()
    )

    return {
        "session_id": session_id,
        "attendance": [
            {
                "student_id": student.id,
                "student_name": student.name,
                "status": attendance.status,
                "marked_at": attendance.marked_at.isoformat(),
            }
            for attendance, student in rows
        ],
    }


@app.get("/batches/{batch_id}/summary")
def get_batch_summary(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("institution")),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if current_user.id != batch.institution_id:
        raise HTTPException(status_code=403, detail="Institution cannot view this batch")

    total_students = db.query(BatchStudent).filter(BatchStudent.batch_id == batch_id).count()
    total_sessions = db.query(Session).filter(Session.batch_id == batch_id).count()

    status_counts = (
        db.query(Attendance.status, func.count(Attendance.id))
        .join(Session, Session.id == Attendance.session_id)
        .filter(Session.batch_id == batch_id)
        .group_by(Attendance.status)
        .all()
    )

    summary = {"present": 0, "absent": 0, "late": 0}
    for key, count in status_counts:
        summary[key] = count

    return {
        "batch_id": batch_id,
        "batch_name": batch.name,
        "total_students": total_students,
        "total_sessions": total_sessions,
        "attendance_counts": summary,
    }


@app.get("/institutions/{institution_id}/summary")
def get_institution_summary(
    institution_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("programme_manager")),
):
    institution = db.query(User).filter(User.id == institution_id, User.role == "institution").first()
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")

    batches = db.query(Batch).filter(Batch.institution_id == institution_id).all()
    batch_ids = [b.id for b in batches]

    total_sessions = db.query(Session).filter(Session.batch_id.in_(batch_ids)).count() if batch_ids else 0
    total_students = (
        db.query(func.count(func.distinct(BatchStudent.student_id)))
        .filter(BatchStudent.batch_id.in_(batch_ids))
        .scalar()
        if batch_ids
        else 0
    )

    attendance_counts = {"present": 0, "absent": 0, "late": 0}
    if batch_ids:
        rows = (
            db.query(Attendance.status, func.count(Attendance.id))
            .join(Session, Session.id == Attendance.session_id)
            .filter(Session.batch_id.in_(batch_ids))
            .group_by(Attendance.status)
            .all()
        )
        for key, count in rows:
            attendance_counts[key] = count

    return {
        "institution_id": institution_id,
        "institution_name": institution.name,
        "total_batches": len(batch_ids),
        "total_sessions": total_sessions,
        "total_students": total_students,
        "attendance_counts": attendance_counts,
    }


@app.get("/programme/summary")
def get_programme_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("programme_manager")),
):
    institution_ids = [
        row[0] for row in db.query(User.id).filter(User.role == "institution").all()
    ]
    batch_ids = [row[0] for row in db.query(Batch.id).all()]

    total_students = db.query(User).filter(User.role == "student").count()
    total_trainers = db.query(User).filter(User.role == "trainer").count()
    total_sessions = db.query(Session).count()

    attendance_counts = {"present": 0, "absent": 0, "late": 0}
    rows = db.query(Attendance.status, func.count(Attendance.id)).group_by(Attendance.status).all()
    for key, count in rows:
        attendance_counts[key] = count

    return {
        "total_institutions": len(institution_ids),
        "total_batches": len(batch_ids),
        "total_trainers": total_trainers,
        "total_students": total_students,
        "total_sessions": total_sessions,
        "attendance_counts": attendance_counts,
    }


@app.get("/monitoring/attendance")
def monitoring_attendance(
    claims: dict = Depends(get_monitoring_claims),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Attendance, Session, User)
        .join(Session, Session.id == Attendance.session_id)
        .join(User, User.id == Attendance.student_id)
        .all()
    )
    return {
        "issued_to_user_id": claims.get("user_id"),
        "count": len(rows),
        "records": [
            {
                "attendance_id": att.id,
                "session_id": sess.id,
                "session_title": sess.title,
                "student_id": stu.id,
                "student_name": stu.name,
                "status": att.status,
                "marked_at": att.marked_at.isoformat(),
            }
            for att, sess, stu in rows
        ],
    }


@app.exception_handler(HTTPException)
def http_exception_handler(_request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
