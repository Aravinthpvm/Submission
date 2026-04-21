import os
import sys
import tempfile
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.auth import hash_password
from src.database import Base, get_db
from src.main import app
from src.models import Batch, BatchStudent, BatchTrainer, Session, User


@pytest.fixture()
def client_and_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            db = TestingSessionLocal()
            try:
                yield client, db
            finally:
                db.close()
                app.dependency_overrides.clear()
                engine.dispose()


@pytest.fixture()
def seeded_users(client_and_db):
    _, db = client_and_db

    institution = User(
        name="Inst User",
        email="inst@test.dev",
        hashed_password=hash_password("Password123!"),
        role="institution",
    )
    trainer = User(
        name="Trainer User",
        email="trainer@test.dev",
        hashed_password=hash_password("Password123!"),
        role="trainer",
    )
    student = User(
        name="Student User",
        email="student@test.dev",
        hashed_password=hash_password("Password123!"),
        role="student",
    )
    monitoring = User(
        name="Monitoring User",
        email="monitor@test.dev",
        hashed_password=hash_password("Password123!"),
        role="monitoring_officer",
    )
    db.add_all([institution, trainer, student, monitoring])
    db.flush()

    trainer.institution_id = institution.id
    student.institution_id = institution.id

    batch = Batch(name="Test Batch", institution_id=institution.id)
    db.add(batch)
    db.flush()

    db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer.id))
    db.add(BatchStudent(batch_id=batch.id, student_id=student.id))

    active_session = Session(
        batch_id=batch.id,
        trainer_id=trainer.id,
        title="Active Session",
        date=date.today(),
        start_time=time(0, 0),
        end_time=time(23, 59),
    )
    db.add(active_session)
    db.commit()

    return {
        "institution": institution,
        "trainer": trainer,
        "student": student,
        "monitoring": monitoring,
        "batch": batch,
        "active_session": active_session,
    }
