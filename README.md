# EVE Healthcare — Diagnostic Test Booking & Payment Backend

Backend REST API for diagnostic test booking and simulated payment processing, built for the **EVE Healthcare SDE Intern Backend Engineering Assignment**.

Demonstrates clean modular architecture, server-side price derivation, transactional consistency, payment gateway abstraction, audit logging, and idempotent webhook handling.

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
| **Password Hashing** | `app/core/security.py` (bcrypt with unique salt generation per user) |
| **JWT Authentication** | `app/core/security.py`, `app/dependencies/auth.py` (HTTP Bearer JWT) |
| **Refresh Tokens & Logout** | `app/routers/auth.py`, `app/core/security.py` (Redis JTI blocklist) |
| **Request Validation** | Pydantic v2 models in `app/schemas/` (strict validation, regex, future date checks, enums) |
| **Diagnostic Centres & Tests** | `app/routers/centres.py`, `app/routers/tests.py`, `app/services/centre_service.py`, `app/services/test_service.py` |
| **Centre/Test Pricing** | `app/models/centre_test.py` (association table with CHECK constraint `price > 0`) |
| **Test Booking** | `app/routers/bookings.py`, `app/services/booking_service.py`, `app/models/booking.py` |
| **Server-side Price Derivation** | `app/services/booking_service.py` (`create_booking` fetches price from DB; client amount ignored) |
| **Booking Status State Machine** | `app/models/booking.py` (`BookingStatus`: `PENDING` → `CONFIRMED` / `FAILED` / `CANCELLED`) |
| **Payment Gateway Abstraction** | `app/integrations/payments/` (`PaymentGateway` Protocol & `SimulatedPaymentGateway`) |
| **Simulated Payment** | `app/routers/payments.py`, `app/services/payment_service.py`, `app/models/payment.py` |
| **Payment Webhook** | `app/routers/payments.py` (`POST /api/v1/payments/webhook`), `app/services/payment_service.py` |
| **Webhook Idempotency** | `app/models/payment.py` (`provider_event_id` `UNIQUE` index), `app/services/payment_service.py` |
| **Audit Logging** | `app/models/audit_log.py`, `app/services/audit_service.py` (`audit_logs` table) |
| **Authorization / Ownership** | `app/dependencies/auth.py`, `app/services/booking_service.py` (HTTP 403 on IDOR) |
| **Edge-Case Handling** | `app/services/booking_service.py`, `app/services/payment_service.py`, `app/utils/exceptions.py` |
| **Redis Caching (Bonus)** | `app/cache/centre_cache.py` (cache-aside pattern with graceful degradation) |
| **Rate Limiting (Bonus)** | `app/utils/rate_limiter.py` (atomic fixed-window counter via Redis pipeline: Login & Payments) |
| **Celery Tasks (Bonus)** | `app/tasks/celery_app.py`, `app/tasks/payment_tasks.py`, `app/tasks/notification_tasks.py` |
| **Database Migrations** | `alembic/versions/001_initial.py`, `alembic/versions/002_add_audit_logs.py`, `alembic.ini` |
| **Docker & Compose** | `Dockerfile`, `docker-compose.yml` |
| **Automated Tests** | `tests/unit/`, `tests/integration/`, `tests/conftest.py`, `pytest.ini` (126 tests, 94% coverage) |

---

## API Endpoints

All 18 routes are documented and accessible via Swagger UI (`/docs`):

| Method | Endpoint | Auth Required | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | No | Register a new user account (unique email, bcrypt password) |
| `POST` | `/api/v1/auth/login` | No | Authenticate with email/password; returns access + refresh tokens (rate-limited) |
| `POST` | `/api/v1/auth/refresh` | No | Exchange valid refresh token for a new access token |
| `POST` | `/api/v1/auth/logout` | **Yes** (Bearer JWT) | Revoke access token (adds JTI to Redis blocklist) |
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
| `POST` | `/api/v1/payments` | **Yes** (Bearer JWT) | Simulate payment (`SUCCESS` or `FAILED`; atomic status transition; rate-limited) |
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
                    │  Adapters    │────▶│    Redis     │
                    │  Dependencies│     │  (Cache +    │
                    └──────┬───────┘     │  Rate Limit) │
                           │             └──────────────┘
                           ▼
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
├── models/         # SQLAlchemy ORM entities (User, Centre, Test, CentreTest, Booking, Payment, AuditLog)
├── schemas/        # Pydantic v2 schemas for request validation and response serialization
├── routers/        # FastAPI thin route handlers (auth, centres, tests, bookings, payments)
├── services/       # Core business logic (price derivation, state machine, idempotency, audit)
├── repositories/   # Data access layer (queries, transactions, eager loading)
├── integrations/   # External provider adapters (PaymentGateway Protocol & SimulatedPaymentGateway)
├── dependencies/   # Dependency injection (HTTP Bearer JWT auth, DB session)
├── tasks/          # Celery application and background worker tasks
├── cache/          # Redis cache-aside helpers with graceful fallback
└── utils/          # Rate limiter, pagination, and HTTP domain exceptions
```

---

## Database Design

### Entity Relationship Diagram

```
Users 1───────────N Bookings 1───────────1 Payments
  │                     │
  │                     │
  │               AuditLogs (actor FK to users)
  │
DiagnosticCentres 1───N CentreTests N───1 DiagnosticTests
                        │
                  Bookings (FK to centres + tests)
```

### Tables & Key Constraints

| Table | Primary Key | Key Foreign Keys & Constraints |
|---|---|---|
| `users` | UUID (`id`) | `email` UNIQUE + indexed, `hashed_password` |
| `diagnostic_centres` | UUID (`id`) | `name` indexed, `location` |
| `diagnostic_tests` | UUID (`id`) | `name` UNIQUE |
| `centre_tests` | UUID (`id`) | `centre_id` FK, `test_id` FK, `UNIQUE(centre_id, test_id)`, `price > 0` |
| `bookings` | UUID (`id`) | `user_id` FK, `centre_id` FK, `test_id` FK, `status` enum, `amount > 0` |
| `payments` | UUID (`id`) | `booking_id` FK (`UNIQUE`), `provider_event_id` (`UNIQUE`), `amount > 0` |
| `audit_logs` | UUID (`id`) | `actor_user_id` FK (ondelete `SET NULL`), `event_type` indexed, `created_at` indexed |

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
- Attempting to pay or cancel an already transitioned booking raises `409 Conflict` or `400 Bad Request`.

### 3. Payment Gateway Abstraction & Simulator
To decouple business logic from provider-specific details, payments use the Adapter pattern:
- **Interface Protocol** (`app/integrations/payments/interface.py`): Defines `PaymentGateway` Protocol returning a structured `GatewayChargeResult` with `provider_event_id` and status.
- **Simulator** (`app/integrations/payments/simulator.py`): In-process deterministic simulator with zero DB access. Controlled via `simulate_status="SUCCESS"` or `"FAILED"`.
- **Production Readiness**: Replacing the simulator with a real gateway (e.g. Stripe, Razorpay) requires implementing the Protocol without changing `PaymentService`.

### 4. Webhook Idempotency & Concurrency Safety
External payment gateways use at-least-once delivery; network retries can send the same webhook event multiple times.

The system uses a two-tier idempotency defense:
1. **Application Query Check (Read Path)**:
   The service queries `payments` by `provider_event_id`. If already recorded, it immediately returns the existing payment record with `200 OK` without re-executing business logic.
2. **Database UNIQUE Constraint (Write Path)**:
   `payments.provider_event_id` has a database-level `UNIQUE` index. If two identical webhook requests arrive concurrently, the second insert encounters an `IntegrityError`, triggering a rollback and returning the existing record safely.
3. **Payload Verification**:
   The webhook verifies that `amount` matches `booking.amount` using `Decimal` comparison. Mismatched amounts raise `400 Bad Request`.

### 5. Redis Cache-Aside & Graceful Degradation
- **Cache-Aside**: Read requests check Redis first. On cache miss, data is read from PostgreSQL and stored in Redis with a configurable TTL (default 300s).
- **Graceful Degradation**: Redis is treated as an optimization layer, not a source of truth. If Redis is unreachable, all cache operations catch the connection error, log a warning, and fall back to PostgreSQL directly. The application remains fully operational.
- **Cache Keys**: Central catalogue data uses shared keys (`centres:list:*`, `tests:list:*`). User-specific resources (such as future patient reports) follow the isolated schema `user:{user_id}:{resource}`.

### 6. Atomic Fixed-Window Rate Limiting
- **Algorithm**: Redis fixed-window counter using atomic `pipeline(MULTI/EXEC)` combining `INCR` and `EXPIRE`.
- **Login Protection**: `rate_limit:login:{client_ip}` limits unauthenticated login requests to 5 attempts per 60 seconds.
- **Payment Protection**: `rate_limit:payment:{user_id}` limits authenticated payment requests to 10 attempts per 60 seconds per user.
- **Graceful Degradation**: If Redis is offline, rate limiting logs a warning and allows requests through to avoid service outages.

### 7. Database Audit Logging
- **Dedicated Table**: `audit_logs` table in PostgreSQL tracks security and business lifecycle events.
- **Captured Events**: `USER_SIGNUP`, `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `BOOKING_CREATED`, `BOOKING_CANCELLED`, `PAYMENT_SUCCESS`, `PAYMENT_FAILED`, `WEBHOOK_PROCESSED`, `WEBHOOK_DUPLICATE`.
- **Fire-and-Forget Safety**: Exceptions during audit logging are caught and isolated so business operations never fail due to an audit write issue.
- **Privacy & Security**: Passwords, JWTs, refresh tokens, and secrets are strictly excluded from audit metadata.

### 8. CORS & Origin Management
- **Environment Driven**: Configured via `CORS_ALLOWED_ORIGINS` environment variable.
- **Production Security**: Restrictive by default (`[]` unless explicit origins configured).
- **Swagger Compatibility**: Swagger UI is served from the same Railway origin, ensuring zero CORS friction.

---

## Production vs Assignment Scope

| Feature | Current Assignment Deployment | Production Scaled Architecture |
|---|---|---|
| **API Server** | Single FastAPI instance on Railway container | Multiple stateless FastAPI instances behind an ALB/Nginx |
| **Database** | Managed PostgreSQL on Railway (ACID, row-level locks) | Managed PostgreSQL with Read Replicas & Connection Pooling (PgBouncer) |
| **Cache & Queue** | Single Redis instance on Railway | High-Availability Redis Cluster (Sentinel or AWS ElastiCache) |
| **Background Tasks** | Celery worker infrastructure implemented locally | Dedicated scalable Celery worker services deployed on Railway/ECS |
| **Payment Gateway** | `SimulatedPaymentGateway` adhering to `PaymentGateway` protocol | Real gateway adapter (Stripe / Razorpay) with HMAC webhook signature checks |
| **Rate Limiting** | Fixed-window counter with Redis pipeline | Sliding-window log or token-bucket at API gateway/Cloudflare tier |

---

## Production Verification Summary

The live Railway deployment ([https://evehealthcare-production.up.railway.app](https://evehealthcare-production.up.railway.app/)) has been verified across all core workflows:

- [x] **Liveness & Readiness**: `GET /health` returns `200 OK`; `GET /ready` verifies PostgreSQL connection pool.
- [x] **Authentication Flow**: User signup with bcrypt hashing; login returns valid signed JWT Bearer token; rate-limiting active.
- [x] **Protected Endpoints**: `GET /api/v1/auth/me` verifies identity; rejects unauthenticated requests with `401 Unauthorized`.
- [x] **Centre & Test Catalog**: Paginated listing of centres and tests with centre-specific pricing; served via Redis cache-aside.
- [x] **Booking Creation**: Server derives pricing from `centre_tests`; rejects past appointment timestamps with `400 Bad Request`.
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
============================= 126 passed in 29.50s =============================
```

- **Total Tests**: 126 (100% passing, 0 warnings, 0 failures)
- **Code Coverage**: 94% total coverage (1,364 statements, 81 missed)
  - `app/integrations/payments/`: 100%
  - `app/cache/centre_cache.py`: 100%
  - `app/dependencies/auth.py`: 100%
  - `app/models/`: 100%
  - `app/schemas/`: 100%
  - `app/services/audit_service.py`: 92%
  - `app/services/booking_service.py`: 95%
  - `app/services/centre_service.py`: 100%
  - `app/services/test_service.py`: 100%
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
| `REFRESH_TOKEN_EXPIRE_DAYS` | Lifetime of refresh tokens | `7` |
| `ENVIRONMENT` | Environment name | `development` / `production` |
| `LOG_LEVEL` | Application logging level | `INFO` |
| `RATE_LIMIT_LOGIN_ATTEMPTS` | Allowed login attempts per window | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Window duration in seconds | `60` |
| `RATE_LIMIT_PAYMENT_ATTEMPTS`| Allowed payment attempts per user per window | `10` |
| `RATE_LIMIT_PAYMENT_WINDOW_SECONDS` | Payment window duration in seconds | `60` |
| `CACHE_TTL_SECONDS` | Cache expiration in seconds | `300` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed CORS origins | `""` (empty for restrictive production) |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result storage | `redis://localhost:6379/1` |
| `PORT` | Web server port | `8000` |

---

## Security Notes

1. **Secrets Management**: Secrets (`SECRET_KEY`, credentials) are supplied exclusively via environment variables. The `.env` file is excluded from git tracking via `.gitignore`.
2. **Production Keys**: The `SECRET_KEY` default placeholder in `.env.example` must be replaced with a cryptographically secure random value in production.
3. **Password Security**: Passwords are never stored in plaintext. They are hashed using bcrypt, which generates and embeds a cryptographically unique salt with every password.
4. **Audit Integrity**: Business and security events are logged to the `audit_logs` table for traceability. Sensitive credentials (passwords, tokens) are never stored in audit metadata.
5. **Webhook Verification**: In commercial production environments, webhook endpoints should validate HMAC-SHA256 provider signatures (e.g. `Stripe-Signature` or `X-Razorpay-Signature`). In this simulated backend, webhook idempotency and amount integrity are enforced at the database and service layers.
6. **Non-Root Container**: The Docker container executes under an unprivileged `appuser` system account.
