from src.auth import decode_token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_student_signup_and_login_returns_jwt(client_and_db):
    client, _ = client_and_db
    signup_payload = {
        "name": "New Student",
        "email": "newstudent@test.dev",
        "password": "Password123!",
        "role": "student",
    }
    signup_res = client.post("/auth/signup", json=signup_payload)
    assert signup_res.status_code == 200
    signup_token = signup_res.json()["access_token"]
    signup_claims = decode_token(signup_token)
    assert signup_claims["role"] == "student"

    login_res = client.post(
        "/auth/login",
        json={"email": "newstudent@test.dev", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    login_token = login_res.json()["access_token"]
    login_claims = decode_token(login_token)
    assert login_claims["role"] == "student"
    assert "exp" in login_claims


def test_trainer_creates_session_with_required_fields(client_and_db, seeded_users):
    client, _ = client_and_db

    login = client.post(
        "/auth/login",
        json={"email": seeded_users["trainer"].email, "password": "Password123!"},
    )
    trainer_token = login.json()["access_token"]

    payload = {
        "batch_id": seeded_users["batch"].id,
        "title": "Intro to APIs",
        "date": "2026-01-15",
        "start_time": "10:00:00",
        "end_time": "11:30:00",
    }
    res = client.post("/sessions", json=payload, headers=auth_header(trainer_token))
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Intro to APIs"


def test_student_marks_own_attendance_successfully(client_and_db, seeded_users):
    client, _ = client_and_db

    login = client.post(
        "/auth/login",
        json={"email": seeded_users["student"].email, "password": "Password123!"},
    )
    student_token = login.json()["access_token"]

    payload = {
        "session_id": seeded_users["active_session"].id,
        "status": "present",
    }
    res = client.post("/attendance/mark", json=payload, headers=auth_header(student_token))
    assert res.status_code == 201
    assert res.json()["status"] == "present"


def test_post_to_monitoring_attendance_returns_405(client_and_db, seeded_users):
    client, _ = client_and_db

    login = client.post(
        "/auth/login",
        json={"email": seeded_users["monitoring"].email, "password": "Password123!"},
    )
    access_token = login.json()["access_token"]

    token_res = client.post(
        "/auth/monitoring-token",
        json={"key": "monitoring-key-123"},
        headers=auth_header(access_token),
    )
    monitor_token = token_res.json()["access_token"]

    res = client.post("/monitoring/attendance", headers=auth_header(monitor_token))
    assert res.status_code == 405


def test_protected_endpoint_without_token_returns_401(client_and_db):
    client, _ = client_and_db
    res = client.post(
        "/batches",
        json={"name": "No Auth Batch", "institution_id": 1},
    )
    assert res.status_code == 401
