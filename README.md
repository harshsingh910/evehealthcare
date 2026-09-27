# EVE Healthcare — Diagnostic Test Booking & Payment Backend

Backend REST API for diagnostic test booking and simulated payment processing, built for the **EVE Healthcare SDE Intern Backend Engineering Assignment**.

Demonstrates clean modular architecture, server-side price derivation, transactional consistency, and idempotent webhook handling.

---

## Live Production Deployment

| Service | URL |
|---|---|
| **Base API** | [https://evehealthcare-production.up.railway.app](https://evehealthcare-production.up.railway.app/) |
| **Interactive Swagger UI** | [https://evehealthcare-production.up.railway.app/docs](https://evehealthcare-production.up.railway.app/docs) |
| **ReDoc Documentation** | [https://evehealthcare-production.up.railway.app/redoc](https://evehealthcare-production.up.railway.app/redoc) |
| **Liveness Probe** | [https://evehealthcare-production.up.railway.app/health](https://evehealthcare-production.up.railway.app/health) |
| **Readiness Probe** | [https://evehealthcare-production.up.railway.app/ready](https://evehealthcare-production.up.railway.app/ready) |

---

## Assignment Requirement Mapping

| Requirement | Implementation Files / Paths |
|---|---|
| **User Signup & Login** | `app/routers/auth.py`, `app/services/auth_service.py`, `app/schemas/auth.py` |
| **JWT Authentication** | `app/core/security.py`, `app/dependencies/auth.py` (HTTP Bearer JWT) |
| **Request Validation** | Pydantic v2 models in `app/schemas/` (strict validation, regex, future date checks) |
| **Diagnostic Centres & Tests** | `app/routers/centres.py`, `app/routers/tests.py`, `app/services/centre_service.py`, `app/services/test_service.py` |
| **Centre/Test Pricing** | `app/models/centre_test.py` (association table with CHECK constraint `price > 0`) |
| **Test Booking** | `app/routers/bookings.py`, `app/services/booking_service.py`, `app/models/booking.py` |
| **Server-side Price Derivation** | `app/services/booking_service.py` (`create_booking` fetches price from DB; client amount ignored) |
| **Booking Status State Machine** | `app/models/booking.py` (`BookingStatus`: `PENDING` → `CONFIRMED` / `FAILED` / `CANCELLED`) |
| **Simulated Payment** | `app/routers/payments.py`, `app/services/payment_service.py`, `app/models/payment.py` |
| **Payment Webhook** | `app/routers/payments.py` (`POST /api/v1/payments/webhook`), `app/services/payment_service.py` |
| **Webhook Idempotency** | `app/models/payment.py` (`provider_event_id` `UNIQUE` index), `app/services/payment_service.py` |
| **Authorization / Ownership** | `app/dependencies/auth.py`, `app/services/booking_service.py` (HTTP 403 on IDOR) |
| **Edge-Case Handling** | `app/services/booking_service.py`, `app/services/payment_service.py`, `app/utils/exceptions.py` |
| **Redis Caching (Bonus)** | `app/cache/centre_cache.py` (cache-aside pattern with graceful degradation) |
| **Rate Limiting (Bonus)** | `app/routers/auth.py` (Redis sliding window counter: 5 attempts / 60s per IP) |
| **Celery Tasks (Bonus)** | `app/tasks/celery_app.py`, `app/tasks/payment_tasks.py`, `app/tasks/notification_tasks.py` |
| **Database Migrations (Bonus)**| `alembic/versions/001_initial.py`, `alembic.ini` |
| **Docker & Compose (Bonus)** | `Dockerfile`, `docker-compose.yml` |
| **Automated Tests** | `tests/unit/`, `tests/integration/`, `tests/conftest.py`, `pytest.ini` (107 tests) |

---

## API Endpoints

All 16 routes are documented and accessible via Swagger UI (`/docs`):

| Method | Endpoint | Auth Required | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | No | Register a new user account (unique email, bcrypt password) |
| `POST` | `/api/v1/auth/login` | No | Authenticate with email/password; returns JWT Bearer token (rate-limited) |
| `GET` | `/api/v1/auth/me` | **Yes** (Bearer JWT) | Retrieve authenticated user profile |
| `GET` | `/api/v1/centres` | No | List diagnostic centres (paginated, Redis cache-aside) |
| `GET` | `/api/v1/centres/{centre_id}` | No | Get centre details with offered tests and pricing |
| `GET` | `/api/v1/centres/{centre_id}/tests` | No | List tests available at a centre with centre-specific prices |
| `GET` | `/api/v1/tests` | No | List diagnostic tests (paginated, optional `centre_id` filter) |
| `GET` | `/api/v1/tests/{test_id}` | No | Get test details with all centres offering it |
| `POST` | `/api/v1/bookings` | **Yes** (Bearer JWT) | Create a test booking (server derives price; validates future date) |
| `GET` | `/api/v1/bookings` | **Yes** (Bearer JWT) | List authenticated user's own bookings |
| `GET` | `/api/v1/bookings/{booking_id}` | **Yes** (Bearer JWT) | Get booking details (scoped to owner; 403 on IDOR) |
| `POST` | `/api/v1/bookings/{booking_id}/cancel` | **Yes** (Bearer JWT) | Cancel booking (only if status is `PENDING`; scoped to owner) |
| `POST` | `/api/v1/payments` | **Yes** (Bearer JWT) | Simulate payment (`SUCCESS` or `FAILED`; atomic status transition) |
| `POST` | `/api/v1/payments/webhook` | No (Provider) | Idempotent payment webhook (deduplicated by `provider_event_id`) |
| `GET` | `/health` | No | Liveness probe (HTTP 200 process alive) |
| `GET` | `/ready` | No | Readiness probe (verifies PostgreSQL connection; non-critical Redis check) |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client    │────▶│   FastAPI    │────▶│  PostgreSQL  │
│ (curl / UI) │     │  (Uvicorn)   │     │ (Source of   │
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
                    │   Worker     │
                    │ (Background  │
                    │    Tasks)    │
                    └──────────────┘
```

### Modular Monolith Structure

```
app/
├── core/           # Database engine, security (JWT/bcrypt), Redis client, logging, settings
├── models/         # SQLAlchemy ORM entities (User, Centre, Test, CentreTest, Booking, Payment)
├── schemas/        # Pydantic v2 schemas for request validation and response serialization
├── routers/        # FastAPI thin route handlers (auth, centres, tests, bookings, payments)
├── services/       # Core business logic (price derivation, state machine, idempotency)
├── repositories/   # Data access layer (queries, transactions, eager loading)
├── dependencies/   # Dependency injection (HTTP Bearer JWT auth, DB session)
├── tasks/          # Celery application and background worker tasks
├── cache/          # Redis cache-aside helpers with graceful fallback
└── utils/          # Standardized pagination and HTTP domain exceptions
```

---

## Database Design

### Entity Relationship Diagram

```
Users 1───────────N Bookings 1───────────1 Payments
                        │
DiagnosticCentres 1───N CentreTests N───1 DiagnosticTests
                        │
                  Bookings (FK to centres + tests)
```

### Tables & Key Constraints

| Table | Primary Key | Key Foreign Keys & Constraints |
|---|---|---|
| `users` | UUID (`id`) | `email` UNIQUE + indexed |
| `diagnostic_centres` | UUID (`id`) | `name` indexed, `location` |
| `diagnostic_tests` | UUID (`id`) | `name` UNIQUE |
| `centre_tests` | UUID (`id`) | `centre_id` FK, `test_id` FK, `UNIQUE(centre_id, test_id)`, `price > 0` |
| `bookings` | UUID (`id`) | `user_id` FK, `centre_id` FK, `test_id` FK, `status` enum, `amount > 0` |
| `payments` | UUID (`id`) | `booking_id` FK (`UNIQUE`), `provider_event_id` (`UNIQUE`), `amount > 0` |

### Why `centre_tests` Exists (Centre-Specific Pricing)

Diagnostic tests (e.g. Complete Blood Count) are standardized, but physical centres operate with differing costs and pricing structures.

Storing price inside `centre_tests` decouples the test definition from its cost:
- A test exists independently in `diagnostic_tests`.
- A centre offers tests through `centre_tests` with its own specific price.
- **Example from seed data** (`scripts/seed_data.py`):
  - *Complete Blood Count (CBC)* at **Apollo Diagnostics**: ₹500.00
  - *Complete Blood Count (CBC)* at **Dr. Lal PathLabs**: ₹400.00
  - *Complete Blood Count (CBC)* at **Thyrocare**: ₹350.00
- The `UNIQUE(centre_id, test_id)` constraint prevents duplicate offerings of the same test by a centre.

---

## Core Technical Explanations

### 1. Server-Side Price Derivation & Snapshot Pattern
- The booking creation endpoint (`POST /api/v1/bookings`) accepts only `centre_id`, `test_id`, and `appointment_datetime`.
- The server queries `centre_tests` within the database transaction to retrieve the authoritative price. Client-submitted prices are neither requested nor trusted.
- The derived price is written into `bookings.amount` as a persistent snapshot. Subsequent changes to centre pricing will not alter existing bookings.

### 2. Booking State Machine
```
              ┌───────────────┐
              │    PENDING    │
              └───┬───┬───┬───┘
                  │   │   │
        Payment   │   │   │  Payment
        SUCCESS   │   │   │  FAILED
                  │   │   │
                  ▼   │   ▼
     ┌─────────────┐  │  ┌────────────┐
     │  CONFIRMED  │  │  │   FAILED   │
     └─────────────┘  │  └────────────┘
                      │
             User     │
             Cancels  │
                      ▼
               ┌─────────────┐
               │  CANCELLED  │
               └─────────────┘
```

- Allowed transitions:
  - `PENDING` → `CONFIRMED` (upon payment `SUCCESS`)
  - `PENDING` → `FAILED` (upon payment `FAILED`)
  - `PENDING` → `CANCELLED` (user-initiated cancellation while pending)
- Terminal states: `CONFIRMED`, `FAILED`, and `CANCELLED` cannot transition to any other status.
- Attempting to pay or cancel an already transitioned booking raises `409 Conflict`.

### 3. Webhook Idempotency & Concurrency Safety
External payment gateways use at-least-once delivery; network retries can send the same webhook event multiple times.

The system uses a two-tier idempotency defense:
1. **Application Query Check (Read Path)**:
   The service queries `payments` by `provider_event_id`. If already recorded, it immediately returns the existing payment record with `200 OK` without re-executing business logic.
2. **Database UNIQUE Constraint (Write Path)**:
   `payments.provider_event_id` has a database-level `UNIQUE` index. If two identical webhook requests arrive concurrently, the second insert encounters an `IntegrityError`, triggering a rollback and returning the existing record safely.
3. **Payload Verification**:
   The webhook verifies that `amount` matches `booking.amount` using `Decimal` comparison. Mismatched amounts raise `400 Bad Request`.

### 4. Redis Cache-Aside & Graceful Degradation
- **Cache-Aside**: Read requests check Redis first. On cache miss, data is read from PostgreSQL and stored in Redis with a configurable TTL (default 300s).
- **Graceful Degradation**: Redis is treated as an optimization layer, not a source of truth. If Redis is unreachable, all cache operations catch the connection error, log a warning, and fall back to PostgreSQL directly. The application remains fully operational.
- **Rate Limiting**: The login endpoint applies a sliding-window counter (`rate_limit:login:{client_ip}`) limiting unauthenticated requests to 5 attempts per 60 seconds.

### 5. Celery Worker Architecture
- **HTTP Webhook**: The `/api/v1/payments/webhook` endpoint processes incoming events synchronously to provide an immediate deterministic response.
- **Background Tasks**:
  - `app.tasks.payment_tasks.process_webhook_async`: Asynchronous webhook processor with exponential backoff (`countdown = 10 * 2^retries`, max 5 retries). Permanent errors (`NotFoundError`, `BadRequestError`, `ConflictError`) are not retried.
  - `app.tasks.notification_tasks.send_booking_confirmation`: Simulated booking confirmation email/SMS.
  - `app.tasks.notification_tasks.send_payment_receipt`: Simulated payment receipt notification.

---

## Production Verification Summary

The live Railway deployment ([https://evehealthcare-production.up.railway.app](https://evehealthcare-production.up.railway.app/)) has been verified across all core workflows:

- [x] **Liveness & Readiness**: `GET /health` returns `200 OK`; `GET /ready` verifies PostgreSQL connection pool.
- [x] **Authentication Flow**: User signup with bcrypt hashing; login returns valid signed JWT Bearer token; rate-limiting active.
- [x] **Protected Endpoints**: `GET /api/v1/auth/me` verifies identity; rejects unauthenticated requests with `401 Unauthorized`.
- [x] **Centre & Test Catalog**: Paginated listing of centres and tests with centre-specific pricing; served via Redis cache-aside.
- [x] **Booking Creation**: Server derives pricing from `centre_tests`; rejects past appointment timestamps with `422`.
- [x] **Authorization & IDOR Protection**: Users can only view and cancel their own bookings; foreign IDs return `403 Forbidden`.
- [x] **Simulated Payment**: Validates booking status; transitions `PENDING` → `CONFIRMED` on `SUCCESS`, `PENDING` → `FAILED` on `FAILED`.
- [x] **Duplicate Payment Guard**: Rejects subsequent payments on the same booking with `409 Conflict`.
- [x] **Webhook Idempotency**: Repeated webhook deliveries with identical `provider_event_id` return existing record without duplicate state changes.
- [x] **Interactive Documentation**: Swagger UI exposes `BearerAuth (http, Bearer)` dialog for direct token testing.

---

## Test Suite & Coverage

The test suite runs against SQLite without requiring external dependencies:

```bash
# Run full test suite with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

### Verified Test Results
```
============================= 107 passed in 26.84s =============================
```

- **Total Tests**: 107 (100% passing, 0 warnings, 0 failures)
- **Code Coverage**: 96% total coverage (1,097 statements, 48 missed)
  - `app/cache/centre_cache.py`: 100%
  - `app/core/security.py`: 100%
  - `app/dependencies/auth.py`: 100%
  - `app/models/`: 100%
  - `app/schemas/`: 100%
  - `app/services/auth_service.py`: 100%
  - `app/services/centre_service.py`: 100%
  - `app/services/test_service.py`: 100%
  - `app/services/booking_service.py`: 97%
  - `app/services/payment_service.py`: 85%
  - `app/tasks/`: 100%
  - `app/utils/`: 100%

---

## Local Setup Instructions

### Prerequisites
- Python 3.12+
- Docker and Docker Compose (optional for containerized setup)

### Clone the Repository
```bash
git clone https://github.com/harshsingh910/evehealthcare.git
cd evehealthcare
```

### Option A: Docker Compose (Full Stack)
Starts PostgreSQL 16, Redis 7, the FastAPI backend, and the Celery worker:

```bash
# 1. Build and start containers
docker compose up --build -d

# 2. Run database migrations
docker compose exec api alembic upgrade head

# 3. Seed initial centres and tests (5 centres, 8 tests, 37 price entries)
docker compose exec api python -m scripts.seed_data

# 4. Verify deployment
curl http://localhost:8000/health
```

### Option B: Local Python Environment
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Run database migrations
alembic upgrade head

# 5. Populate seed data (idempotent)
python -m scripts.seed_data

# 6. Start the API server
uvicorn app.main:app --reload --port 8000
```

To start the optional Celery worker locally:
```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## Environment Variables

| Variable | Description | Default / Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://eve_user:eve_password@localhost:5432/eve_healthcare` |
| `REDIS_URL` | Redis cache connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | HMAC-SHA256 secret key for JWT | Configured via environment; placeholder in `.env.example` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of access tokens | `30` |
| `ENVIRONMENT` | Environment name | `development` / `production` |
| `LOG_LEVEL` | Application logging level | `INFO` |
| `RATE_LIMIT_LOGIN_ATTEMPTS` | Allowed login attempts per window | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Window duration in seconds | `60` |
| `CACHE_TTL_SECONDS` | Cache expiration in seconds | `300` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result storage | `redis://localhost:6379/1` |
| `PORT` | Web server port | `8000` |

---

## Railway Deployment Details

The production Railway deployment consists of:
1. **API Service**: Runs the FastAPI application (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`) via the container defined in [Dockerfile](file:///Users/harshsingh/Documents/EveHealthCare/Dockerfile).
2. **PostgreSQL Service**: Railway managed PostgreSQL instance for ACID transaction persistence.
3. **Redis Service**: Railway managed Redis instance for caching and rate limiting.
4. **Celery Worker (Optional)**: A separate worker service can be deployed by configuring a service in Railway with start command:
   ```bash
   celery -A app.tasks.celery_app worker --loglevel=info
   ```

---

## Security Notes

1. **Secrets Management**: Secrets (`SECRET_KEY`, credentials) are supplied exclusively via environment variables. The `.env` file is excluded from git tracking via `.gitignore`.
2. **Production Keys**: The `SECRET_KEY` default placeholder in `.env.example` must be replaced with a cryptographically secure random value in production.
3. **Webhook Verification**: In commercial production environments, webhook endpoints should validate HMAC-SHA256 provider signatures (e.g. `Stripe-Signature` or `X-Razorpay-Signature`). In this simulated backend, webhook idempotency and amount integrity are enforced at the database and service layers.
4. **Non-Root Container**: The Docker container executes under an unprivileged `appuser` system account.
