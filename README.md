# EVE Healthcare — Diagnostic Test Booking Backend

> Production-grade backend for diagnostic test booking and simulated payment processing.
> Built as an SDE Intern hiring assignment demonstrating clean architecture, transactional consistency, and idempotent webhook handling.

---

## Overview

A FastAPI-based REST API that allows users to:

1. **Sign up / Log in** with JWT authentication
2. **Browse diagnostic centres** and their test offerings with centre-specific pricing
3. **Book diagnostic tests** with server-side price derivation
4. **Pay for bookings** (simulated) with explicit state machine transitions
5. **Receive payment webhooks** with database-level idempotency guarantees

---

## Features

### Required Features
- ✅ User signup & login with JWT authentication
- ✅ Request validation (Pydantic v2)
- ✅ Diagnostic centres & tests with centre-specific pricing
- ✅ Authenticated diagnostic test booking
- ✅ Booking status management (state machine)
- ✅ Simulated payment (SUCCESS / FAILED)
- ✅ Payment webhook with idempotent processing
- ✅ Proper authorization (users can only access own bookings)
- ✅ Edge-case handling

### Bonus Features
- ✅ Redis caching (cache-aside pattern with graceful degradation)
- ✅ Redis-based rate limiting (login endpoint)
- ✅ Celery background jobs (async webhook processing with retries)
- ✅ Docker & Docker Compose (API, PostgreSQL, Redis, Worker)
- ✅ Swagger/OpenAPI documentation (`/docs`, `/redoc`)
- ✅ Unit tests (auth, booking, payment services)
- ✅ Integration tests (all endpoints, webhooks, edge cases)
- ✅ Structured JSON logging with request IDs
- ✅ Pagination (SQL-level OFFSET/LIMIT)
- ✅ Webhook retry handling (exponential backoff)
- ✅ Railway deployment readiness

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client    │────▶│   FastAPI    │────▶│  PostgreSQL  │
│  (curl/UI)  │     │   (Uvicorn)  │     │  (Source of  │
└─────────────┘     │              │     │    Truth)    │
                    │  Routers     │     └──────────────┘
                    │  Services    │
                    │  Repositories│     ┌──────────────┐
                    │  Dependencies│────▶│    Redis     │
                    └──────┬───────┘     │  (Cache +    │
                           │             │  Rate Limit) │
                           ▼             └──────────────┘
                    ┌──────────────┐
                    │    Celery    │
                    │   Worker    │
                    │ (Background │
                    │   Tasks)    │
                    └──────────────┘
```

**Modular Monolith** — clean separation without microservice overhead:

```
app/
├── core/           # Config, DB, security, Redis, logging
├── models/         # SQLAlchemy ORM models
├── schemas/        # Pydantic request/response schemas
├── routers/        # FastAPI route handlers (thin)
├── services/       # Business logic (state machine, validation)
├── repositories/   # Data access layer (queries, transactions)
├── dependencies/   # FastAPI dependency injection (auth, DB session)
├── tasks/          # Celery background tasks
├── cache/          # Redis cache-aside helpers
└── utils/          # Pagination, exceptions
```

---

## Technology Stack

| Technology | Purpose |
|---|---|
| **FastAPI + Uvicorn** | High-performance async web framework |
| **PostgreSQL** | ACID transactions, UNIQUE constraints for idempotency, row-level locking |
| **SQLAlchemy 2.x** | Type-safe ORM with relationship mapping |
| **Alembic** | Database schema migrations (never `create_all()` in production) |
| **Pydantic v2** | Request validation, response serialization |
| **JWT (python-jose)** | Stateless authentication with Bearer tokens |
| **bcrypt (passlib)** | Industry-standard password hashing |
| **Redis** | Cache-aside layer + rate limiting (NOT source of truth) |
| **Celery** | Background task processing with retry support |
| **Docker Compose** | Local development with PostgreSQL, Redis, API, Worker |
| **pytest** | Unit + integration test suite |

---

## Database Design

### Entity Relationship Diagram

```
Users 1───N Bookings 1───1 Payments
                │
DiagnosticCentres 1───N CentreTests N───1 DiagnosticTests
                │
        Bookings (FK to centres + tests)
```

### Tables

| Table | Purpose |
|---|---|
| `users` | User accounts (UUID PK, unique indexed email, bcrypt password) |
| `diagnostic_centres` | Physical diagnostic centres (name, location) |
| `diagnostic_tests` | Types of diagnostic tests (CBC, Thyroid, etc.) |
| `centre_tests` | **Association table** — which tests each centre offers, with **centre-specific pricing** |
| `bookings` | Test bookings with status state machine |
| `payments` | Payment records with `provider_event_id` for webhook idempotency |

### Why `centre_tests` Exists

The same diagnostic test has different prices at different centres:

| Centre | Test | Price |
|---|---|---|
| Apollo Diagnostics | CBC | ₹500 |
| Dr. Lal PathLabs | CBC | ₹400 |
| Thyrocare | CBC | ₹350 |

Price is stored in `centre_tests`, NOT in `diagnostic_tests`. The `UNIQUE(centre_id, test_id)` constraint prevents duplicate offerings.

### Key Constraints

- `centre_tests.price > 0` (CHECK constraint)
- `bookings.amount > 0` (CHECK constraint)
- `payments.booking_id` UNIQUE (one payment per booking)
- `payments.provider_event_id` UNIQUE (webhook idempotency)
- `users.email` UNIQUE + indexed

---

## Booking Flow

```
PENDING ──→ CONFIRMED  (successful payment)
   │
   ├──→ FAILED      (failed payment)
   │
   └──→ CANCELLED   (user cancellation)

CONFIRMED ──→ CANCELLED (user cancellation after payment)

FAILED ──→ (terminal state, no transitions allowed)
CANCELLED ──→ (terminal state, no transitions allowed)
```

**Important:** The booking `amount` is **copied from `centre_tests.price`** at booking creation time. It is NEVER accepted from the client. This is a price snapshot — if the centre later changes the test price, existing bookings are unaffected.

---

## Payment Flow

### Simulated Payment (POST /api/v1/payments)

```
Client sends: { booking_id, simulate_status: "SUCCESS" | "FAILED" }
                              │
                    ┌─────────▼──────────┐
                    │ Validate booking   │
                    │ - exists?          │
                    │ - belongs to user? │
                    │ - status=PENDING?  │
                    │ - no existing pay? │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼                               ▼
    Payment.status=SUCCESS          Payment.status=FAILED
    Booking.status=CONFIRMED        Booking.status=FAILED
              │                               │
              └───────────┬───────────────────┘
                          ▼
                   ATOMIC COMMIT
```

### Webhook Processing (POST /api/v1/payments/webhook)

```
Provider sends: { event_id, booking_id, status, amount }
                              │
              ┌───────────────▼───────────────┐
              │ 1. Check provider_event_id    │
              │    already processed?         │◄── Fast path for duplicates
              │ 2. Lock booking (FOR UPDATE)  │
              │ 3. Validate amount matches    │
              │ 4. Enforce state machine      │
              │ 5. Check no existing payment  │
              │ 6. Create payment             │
              │ 7. Update booking status      │
              │ 8. ATOMIC COMMIT              │
              └───────────────────────────────┘
```

---

## Webhook Idempotency

**Problem:** External payment providers can send the same webhook event multiple times (retries, network issues).

**Solution:** Database-level UNIQUE constraint on `provider_event_id`.

**Why not just application-level checks?**

```
Thread A: SELECT ... WHERE provider_event_id = 'evt_123' → NULL (not found)
Thread B: SELECT ... WHERE provider_event_id = 'evt_123' → NULL (not found)
Thread A: INSERT payment (provider_event_id = 'evt_123') → SUCCESS
Thread B: INSERT payment (provider_event_id = 'evt_123') → UNIQUE VIOLATION → caught safely
```

The application-level check (`if event_exists(): return`) handles the common case efficiently. The database constraint handles the race condition. Both are needed.

---

## Redis

### Cache-Aside Pattern

```
Request → Check Redis → HIT? → Return cached response
                    │
                    └→ MISS → Query PostgreSQL → Store in Redis (TTL=300s) → Return
```

**Cached endpoints:** Centres list, centre detail, tests list, test detail.

### Cache Invalidation

When centre/test/price data changes (via admin operations added later):
1. Update PostgreSQL
2. Invalidate relevant Redis keys
3. Next read repopulates cache

### Rate Limiting

Login endpoint: 5 attempts per minute per IP (configurable).

### Graceful Degradation

**If Redis is unavailable**, the application:
- Queries PostgreSQL directly (no caching)
- Bypasses rate limiting (logs a warning)
- Does NOT crash or return errors

PostgreSQL is always the source of truth.

---

## Celery

### Architecture

```
FastAPI → Enqueue Task → Redis (Broker) → Celery Worker → PostgreSQL
```

### Background Tasks

- **process_webhook_async**: Processes webhook events asynchronously with exponential backoff
- **send_booking_confirmation**: Simulated email notification
- **send_payment_receipt**: Simulated payment receipt

### Retry Behavior

- Max retries: 5
- Backoff: 10s, 20s, 40s, 80s, 160s
- Permanent failures (404, 400, 409) are NOT retried
- Only transient failures (DB errors, connection issues) are retried
- Tasks are **idempotent** — safe to execute more than once

---

## API Documentation

Interactive Swagger UI: `http://localhost:8000/docs`

ReDoc: `http://localhost:8000/redoc`

OpenAPI spec: `http://localhost:8000/openapi.json`

---

## Local Setup

### Option 1: Docker Compose (Recommended)

```bash
# Clone and start all services
git clone <repo-url>
cd eve-healthcare-backend

# Start PostgreSQL, Redis, API, and Celery Worker
docker compose up --build

# Run migrations
docker compose exec api alembic upgrade head

# Seed data
docker compose exec api python -m scripts.seed_data

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

### Option 2: Local Python

```bash
# Prerequisites: PostgreSQL and Redis running locally

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your local PostgreSQL/Redis URLs

# Run migrations
alembic upgrade head

# Seed data
python -m scripts.seed_data

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://eve_user:eve_password@localhost:5432/eve_healthcare` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (**change in production**) | `change-me-...` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `30` |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_LOGIN_ATTEMPTS` | Max login attempts per window | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate limit window duration | `60` |
| `CACHE_TTL_SECONDS` | Redis cache TTL | `300` |
| `CELERY_BROKER_URL` | Celery broker (Redis) | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/1` |
| `PORT` | API server port | `8000` |

---

## Database Migration

```bash
# Apply all migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Generate new migration after model changes
alembic revision --autogenerate -m "description"
```

**NEVER** use `Base.metadata.drop_all()` or `create_all()` in production.

---

## Seed Data

```bash
python -m scripts.seed_data
```

Creates 5 centres, 8 tests, and 35 centre-test price combinations. **Idempotent** — safe to run multiple times.

---

## Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Run only unit tests
python -m pytest tests/unit/ -v

# Run only integration tests
python -m pytest tests/integration/ -v
```

Tests use SQLite — **no PostgreSQL/Redis required** to run the test suite.

---

## Railway Deployment

### Step-by-Step

1. **Create Railway Project**
2. **Add PostgreSQL** service → copy `DATABASE_URL`
3. **Add Redis** service → copy `REDIS_URL`
4. **Deploy API**:
   - Source: GitHub repo
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Set environment variables (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, etc.)
5. **Deploy Worker**:
   - Same source, different start command: `celery -A app.tasks.celery_app worker --loglevel=info`
   - Same environment variables
6. **Run Migrations**: `alembic upgrade head` (via Railway CLI or exec)
7. **Seed Data**: `python -m scripts.seed_data`
8. **Verify**: `GET /health` and `GET /docs`

---

## API Examples

### Signup
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name": "Harsh Singh", "email": "harsh@example.com", "password": "Password@123"}'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "harsh@example.com", "password": "Password@123"}'
```

### List Centres
```bash
curl http://localhost:8000/api/v1/centres?page=1&page_size=10
```

### Get Centre with Tests
```bash
curl http://localhost:8000/api/v1/centres/{centre_id}
```

### List Tests (filter by centre)
```bash
curl "http://localhost:8000/api/v1/tests?centre_id={centre_id}"
```

### Create Booking
```bash
curl -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"centre_id": "...", "test_id": "...", "appointment_datetime": "2026-10-05T10:30:00Z"}'
```

### Simulate Payment
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "...", "simulate_status": "SUCCESS"}'
```

### Webhook
```bash
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_12345", "booking_id": "...", "status": "SUCCESS", "amount": 500}'
```

---

## Edge Cases Handled

| Edge Case | Behavior |
|---|---|
| Duplicate email signup | 409 Conflict |
| Wrong password login | 401 (same message as wrong email — prevents enumeration) |
| Expired/invalid JWT | 401 Unauthorized |
| User A accessing User B's booking | 403 Forbidden |
| Test not offered at centre | 400 Bad Request |
| Appointment in the past | 400 Bad Request |
| Duplicate payment for same booking | 409 Conflict |
| Cancelling a FAILED booking | 400 (state machine violation) |
| FAILED → CONFIRMED via webhook | 400 (invalid state transition) |
| Duplicate webhook (same event_id) | Safely ignored, returns existing payment |
| Concurrent identical webhooks | UNIQUE constraint prevents duplicates |
| Webhook amount ≠ booking amount | 400 Bad Request |
| Page size > 100 | 422 Validation Error |
| Redis unavailable | Graceful degradation to PostgreSQL |

---

## Assumptions

1. One user can create many bookings
2. A diagnostic centre can offer many tests (M:N via centre_tests)
3. Centre-specific pricing is stored in centre_tests
4. Booking amount is copied from centre_test price at creation (snapshot)
5. Booking amount is NEVER controlled by the client
6. Bookings start as PENDING
7. Successful payment → CONFIRMED; failed payment → FAILED
8. One booking has at most one payment record
9. `provider_event_id` uniquely identifies an external webhook event
10. Repeated webhook events are safely ignored (idempotent)
11. PostgreSQL is the source of truth; Redis is NOT authoritative
12. Redis failure does not break booking/payment functionality
13. Payment gateway is simulated (no real integration)
14. Appointment times in the past are rejected

---

## Future Improvements

1. **Admin panel** — CRUD for centres, tests, pricing (with cache invalidation)
2. **Cursor-based pagination** — more efficient for large datasets than OFFSET
3. **Webhook signature verification** — HMAC-SHA256 validation of webhook payloads
4. **Multi-test bookings** — book multiple tests in a single appointment
5. **Appointment slot management** — prevent overbooking at specific times
6. **Email notifications** — SendGrid/SES integration for booking confirmations
7. **Refresh tokens** — JWT refresh token rotation for better security
8. **Role-based access control** — admin vs. patient roles
9. **Audit logging** — immutable log of all state changes
10. **Prometheus metrics** — request latency, error rates, cache hit ratios
