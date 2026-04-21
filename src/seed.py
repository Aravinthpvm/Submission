from datetime import date, datetime, time, timedelta

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import Attendance, Batch, BatchStudent, BatchTrainer, Session, User


def create_user(db, name, email, role, institution_id=None, password="Password123!"):
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        institution_id=institution_id,
    )
    db.add(user)
    db.flush()
    return user


def run_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(User).count() > 0:
        print("Seed skipped: users already exist")
        db.close()
        return

    try:
        institution1 = create_user(db, "North Skill Institute", "inst1@skillbridge.dev", "institution")
        institution2 = create_user(db, "South Skill Academy", "inst2@skillbridge.dev", "institution")

        pm = create_user(db, "Programme Manager", "pm@skillbridge.dev", "programme_manager")
        mo = create_user(db, "Monitoring Officer", "mo@skillbridge.dev", "monitoring_officer")

        trainers = [
            create_user(db, "Trainer One", "trainer1@skillbridge.dev", "trainer", institution1.id),
            create_user(db, "Trainer Two", "trainer2@skillbridge.dev", "trainer", institution1.id),
            create_user(db, "Trainer Three", "trainer3@skillbridge.dev", "trainer", institution2.id),
            create_user(db, "Trainer Four", "trainer4@skillbridge.dev", "trainer", institution2.id),
        ]

        students = []
        for i in range(1, 16):
            institution_id = institution1.id if i <= 8 else institution2.id
            students.append(
                create_user(
                    db,
                    f"Student {i}",
                    f"student{i}@skillbridge.dev",
                    "student",
                    institution_id,
                )
            )

        batch1 = Batch(name="Batch A", institution_id=institution1.id)
        batch2 = Batch(name="Batch B", institution_id=institution1.id)
        batch3 = Batch(name="Batch C", institution_id=institution2.id)
        db.add_all([batch1, batch2, batch3])
        db.flush()

        db.add_all(
            [
                BatchTrainer(batch_id=batch1.id, trainer_id=trainers[0].id),
                BatchTrainer(batch_id=batch1.id, trainer_id=trainers[1].id),
                BatchTrainer(batch_id=batch2.id, trainer_id=trainers[1].id),
                BatchTrainer(batch_id=batch3.id, trainer_id=trainers[2].id),
                BatchTrainer(batch_id=batch3.id, trainer_id=trainers[3].id),
            ]
        )

        for student in students[:6]:
            db.add(BatchStudent(batch_id=batch1.id, student_id=student.id))
        for student in students[6:10]:
            db.add(BatchStudent(batch_id=batch2.id, student_id=student.id))
        for student in students[10:]:
            db.add(BatchStudent(batch_id=batch3.id, student_id=student.id))

        today = date.today()
        session_defs = [
            (batch1.id, trainers[0].id, "Python Basics", today - timedelta(days=2), time(9, 0), time(10, 30)),
            (batch1.id, trainers[1].id, "Git and Collaboration", today - timedelta(days=1), time(10, 0), time(11, 30)),
            (batch1.id, trainers[0].id, "APIs with FastAPI", today, time(9, 0), time(11, 0)),
            (batch2.id, trainers[1].id, "Data Structures", today - timedelta(days=2), time(12, 0), time(13, 0)),
            (batch2.id, trainers[1].id, "SQL Fundamentals", today - timedelta(days=1), time(13, 0), time(14, 0)),
            (batch3.id, trainers[2].id, "Cloud Intro", today - timedelta(days=3), time(9, 30), time(11, 0)),
            (batch3.id, trainers[3].id, "Monitoring and Ops", today - timedelta(days=1), time(11, 0), time(12, 30)),
            (batch3.id, trainers[2].id, "Security Basics", today, time(15, 0), time(16, 30)),
        ]

        sessions = []
        for batch_id, trainer_id, title, d, st, et in session_defs:
            sess = Session(batch_id=batch_id, trainer_id=trainer_id, title=title, date=d, start_time=st, end_time=et)
            db.add(sess)
            db.flush()
            sessions.append(sess)

        enrolled_by_batch = {
            batch1.id: students[:6],
            batch2.id: students[6:10],
            batch3.id: students[10:],
        }

        for sess in sessions:
            for idx, student in enumerate(enrolled_by_batch[sess.batch_id]):
                status = "present"
                if idx % 5 == 0:
                    status = "late"
                elif idx % 4 == 0:
                    status = "absent"
                db.add(
                    Attendance(
                        session_id=sess.id,
                        student_id=student.id,
                        status=status,
                        marked_at=datetime.utcnow() - timedelta(hours=1),
                    )
                )

        db.commit()
        print("Seed completed successfully")
        print("Default password for all seeded accounts: Password123!")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
