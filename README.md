# SkillBridge Attendance API (Take-Home Assignment)

## 1) Live API Base URL and Deployment Notes

- GitHub repository: [Aravinthpvm/Submission](https://github.com/Aravinthpvm/Submission)
- Live base URL: [submission-g5ho.onrender.com](https://submission-g5ho.onrender.com)
- Live docs URL: [submission-g5ho.onrender.com/docs](https://submission-g5ho.onrender.com/docs)
- Live login curl command:

```bash
curl -X POST "https://submission-g5ho.onrender.com/auth/login" -H "Content-Type: application/json" -d '{"email":"trainer1@skillbridge.dev","password":"Password123!"}'
```

- Deployment target tested locally: FastAPI app with PostgreSQL-compatible SQLAlchemy setup
- If deployment is pending, this repository is still runnable and testable locally.

## 2) Local Setup Instructions

1. Create and activate a virtual environment.
1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Copy env file and update values:

```bash
cp .env.example .env
```

1. Optional local quick start with SQLite (no PostgreSQL needed):

- Set `DATABASE_URL=sqlite:///./skillbridge.db` in `.env`.

1. Run seed data:

```bash
python -m src.seed
```

1. Run API:

```bash
uvicorn src.main:app --reload
```

1. Open docs:

- `http://127.0.0.1:8000/docs`

## 3) Seeded Test Accounts (All Roles)

Default password for all seeded users: `Password123!`

- Institution
- `inst1@skillbridge.dev`
- `inst2@skillbridge.dev`
- Trainer
- `trainer1@skillbridge.dev`
- `trainer2@skillbridge.dev`
- `trainer3@skillbridge.dev`
- `trainer4@skillbridge.dev`
- Student
- `student1@skillbridge.dev` ... `student15@skillbridge.dev`
- Programme Manager
- `pm@skillbridge.dev`
- Monitoring Officer
- `mo@skillbridge.dev`

## 4) JWT Payload Structures

### Standard Access Token (24h)

```json
{
  "user_id": 12,
  "role": "trainer",
  "token_type": "access",
  "iat": 1713565200,
  "exp": 1713651600
}
```

### Monitoring Read-Only Token (1h)

```json
{
  "user_id": 22,
  "role": "monitoring_officer",
  "token_type": "monitoring",
  "scope": "monitoring:read",
  "iat": 1713565200,
  "exp": 1713568800
}
```

## 5) Sample curl Commands for Every Endpoint

Set base URL:

```bash
BASE_URL=http://127.0.0.1:8000
```

### Auth

```bash
curl -X POST "$BASE_URL/auth/signup" -H "Content-Type: application/json" -d '{"name":"A Student","email":"astudent@example.com","password":"Password123!","role":"student"}'
```

```bash
curl -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" -d '{"email":"trainer1@skillbridge.dev","password":"Password123!"}'
```

```bash
curl -X POST "$BASE_URL/auth/monitoring-token" -H "Authorization: Bearer <MONITORING_OFFICER_ACCESS_TOKEN>" -H "Content-Type: application/json" -d '{"key":"monitoring-key-123"}'
```

### Batches

```bash
curl -X POST "$BASE_URL/batches" -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d '{"name":"Batch Z","institution_id":1}'
```

```bash
curl -X POST "$BASE_URL/batches/1/invite" -H "Authorization: Bearer <TRAINER_TOKEN>"
```

```bash
curl -X POST "$BASE_URL/batches/join" -H "Authorization: Bearer <STUDENT_TOKEN>" -H "Content-Type: application/json" -d '{"token":"<INVITE_TOKEN>"}'
```

### Sessions

```bash
curl -X POST "$BASE_URL/sessions" -H "Authorization: Bearer <TRAINER_TOKEN>" -H "Content-Type: application/json" -d '{"batch_id":1,"title":"Data Session","date":"2026-05-01","start_time":"09:00:00","end_time":"10:30:00"}'
```

```bash
curl "$BASE_URL/sessions/1/attendance" -H "Authorization: Bearer <TRAINER_TOKEN>"
```

### Attendance

```bash
curl -X POST "$BASE_URL/attendance/mark" -H "Authorization: Bearer <STUDENT_TOKEN>" -H "Content-Type: application/json" -d '{"session_id":1,"status":"present"}'
```

### Summaries

```bash
curl "$BASE_URL/batches/1/summary" -H "Authorization: Bearer <INSTITUTION_TOKEN>"
```

```bash
curl "$BASE_URL/institutions/1/summary" -H "Authorization: Bearer <PROGRAMME_MANAGER_TOKEN>"
```

```bash
curl "$BASE_URL/programme/summary" -H "Authorization: Bearer <PROGRAMME_MANAGER_TOKEN>"
```

```bash
curl "$BASE_URL/monitoring/attendance" -H "Authorization: Bearer <MONITORING_READONLY_TOKEN>"
```

### Method Not Allowed Check (Should return 405)

```bash
curl -X POST "$BASE_URL/monitoring/attendance" -H "Authorization: Bearer <MONITORING_READONLY_TOKEN>"
```

## 6) Schema Decisions

- `batch_trainers`: explicit many-to-many table so multiple trainers can be assigned to one batch and authorization can check trainer-batch assignment directly.
- `batch_invites`: includes `token`, `expires_at`, and `used` for one-time invite flow with expiration.
- Dual-token Monitoring Officer flow:
- login gives normal access token
- `/auth/monitoring-token` requires monitoring API key + monitoring officer login token
- monitoring endpoints accept only scoped monitoring token

## 7) Validation and Error Handling Behavior

- Required field validation relies on FastAPI/Pydantic and returns `422` with descriptive body.
- Foreign key style misses (batch/session/institution/invite not found) return `404` explicitly.
- Student marking attendance for a session outside their batch returns `403`.
- Missing/invalid tokens return `401`.

## 8) Tests

Run:

```bash
pytest -q
```

Included tests:

1. Successful student signup and login with valid JWT assertions.
2. Trainer creating a session with all required fields.
3. Student marking own attendance.
4. POST to `/monitoring/attendance` returns `405`.
5. Protected endpoint request without token returns `401`.

At least two tests use a real test database (SQLite file-backed DB in fixtures), with no full DB mocking.

## 9) Security Notes

### Token Rotation / Revocation (real deployment approach)

- Add a token `jti` claim and store active/revoked JTIs in Redis.
- Rotate signing keys using KID-based key sets and phased key rollover.
- Use short access token TTL + refresh token flow with server-side revocation list.

### Known Security Issue in This Implementation

- Monitoring API key is static and single-value from environment.

How to improve with more time:

- Replace static key with managed secret service and per-user/per-client API keys.
- Add rate limiting and anomaly detection for `/auth/monitoring-token`.

## 10) What Is Working vs Partial

Fully working locally:

- Core schema and all required endpoints
- JWT auth, RBAC checks, monitoring dual-token flow
- Seed script for meaningful summary output
- Required pytest coverage (5 tests)

Partial / not completed:

- Public cloud deployment URL not yet configured

## 11) One Thing I Would Do Differently with More Time

- Introduce Alembic migrations and stricter audit logging (who changed what and when) for all write operations.
