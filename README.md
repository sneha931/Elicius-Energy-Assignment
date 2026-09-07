# AI Q&A Platform

A production-oriented AI Question-Answering API built with **Python, FastAPI, PostgreSQL, Redis, JWT authentication, OpenRouter, Docker, and Prometheus**.

The project demonstrates LLM integration, authentication, caching, distributed rate limiting, timeout/retry/fallback handling, database integration, monitoring, containerization, automated testing, and production scaling considerations.

---

## 1. Assessment Requirements

This project implements the required AI Q&A API with:

* FastAPI
* LLM API integration
* JWT authentication
* PostgreSQL
* Redis
* Docker
* Redis caching
* Redis-based rate limiting
* LLM timeout handling
* Retry and fallback logic
* Request latency tracking
* LLM token usage tracking
* Prometheus metrics
* Health checks
* Automated tests
* Production scaling design
* EC2 to 10,000-user migration design

---

## 2. Architecture

### Current Docker Architecture

```text
                         Client
                           |
                           v
                    +--------------+
                    |   FastAPI    |
                    |     API      |
                    |   :8000      |
                    +------+-------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
      +-------------+             +-------------+
      | PostgreSQL  |             |    Redis    |
      |             |             |             |
      | Users       |             | Cache       |
      | Roles       |             | Rate Limit  |
      +-------------+             +------+------+
                                         |
                                         v
                                  +-------------+
                                  |  OpenRouter |
                                  |     LLM     |
                                  +-------------+
```

### Production Architecture

For production traffic, the API can be deployed as multiple stateless FastAPI instances behind a load balancer:

```text
                         Users
                           |
                           v
                    +--------------+
                    | Load Balancer|
                    +------+-------+
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
         FastAPI       FastAPI       FastAPI
         Instance      Instance      Instance
             |             |             |
             +-------------+-------------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
          Redis                      PostgreSQL
             |
             v
       Queue / LLM Gateway
             |
             v
        LLM Provider
```

The API is stateless, allowing horizontal scaling.

See:

* `docs/architecture.md`
* `docs/scaling.md`
* `docs/migration.md`

---

## 3. Technology Stack

| Component             | Technology              |
| --------------------- | ----------------------- |
| Language              | Python 3.12             |
| API                   | FastAPI                 |
| Server                | Uvicorn                 |
| Database              | PostgreSQL 16           |
| Cache / Rate Limiting | Redis 7                 |
| Authentication        | JWT                     |
| Password Hashing      | bcrypt                  |
| LLM Gateway           | OpenRouter              |
| LLM Client            | OpenAI Python SDK       |
| Monitoring            | Prometheus              |
| Containerization      | Docker / Docker Compose |
| Testing               | pytest                  |

---

## 4. Project Structure

```text
ai_qa_platform/
│
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   └── chat.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── metrics.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── cache.py
│   │   ├── llm.py
│   │   └── rate_limit.py
│   │
│   ├── create_user.py
│   └── main.py
│
├── tests/
│   ├── conftest.py
│   └── test_api.py
│
├── docs/
│   ├── architecture.md
│   ├── scaling.md
│   └── migration.md
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
├── .dockerignore
├── .gitignore
└── README.md
```

---

# 5. Implemented APIs

## POST `/auth/login`

Authenticates a user and returns a JWT access token.

### Request

```json
{
  "username": "admin",
  "password": "admin123"
}
```

### Response

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer"
}
```

The password is verified against the bcrypt hash stored in PostgreSQL.

---

## POST `/chat`

Authenticated AI Question-Answering endpoint.

### Request

```http
Authorization: Bearer <JWT>
```

```json
{
  "question": "What is Kubernetes?"
}
```

### Response

```json
{
  "answer": "Kubernetes is a container orchestration platform...",
  "model": "model-name",
  "tokens": {
    "prompt": 10,
    "completion": 25,
    "total": 35
  },
  "latency_ms": 1250.5
}
```

The endpoint performs:

1. JWT authentication
2. Redis rate-limit check
3. Redis cache lookup
4. LLM request on cache miss
5. Retry for transient failures
6. Fallback model handling
7. Redis cache write
8. Latency calculation
9. Token usage tracking
10. HTTP response

---

## GET `/health`

Checks API dependencies.

Example:

```json
{
  "status": "healthy",
  "dependencies": {
    "postgres": "healthy",
    "redis": "healthy"
  }
}
```

The health endpoint checks PostgreSQL with a simple database query and checks Redis connectivity.

---

## GET `/metrics`

Exposes Prometheus metrics.

Custom metrics include:

```text
llm_requests_total
llm_request_duration_seconds
llm_tokens_total
cache_hits_total
cache_misses_total
rate_limit_exceeded_total
```

FastAPI HTTP request metrics are also exposed.

---

# 6. Authentication and Authorization

The application implements JWT authentication.

After login, the JWT contains:

* User ID
* Username
* Role
* Expiration time

The token is supplied using:

```http
Authorization: Bearer <JWT>
```

Passwords are stored as bcrypt hashes rather than plaintext.

### Production SSO / OIDC

For production, the local JWT login can be replaced or extended with an identity provider:

```text
Application
     |
     v
SSO / OAuth2 / OIDC
     |
     v
Identity Provider
     |
     v
Signed JWT
     |
     v
API Gateway
     |
     v
AI Service
```

The API would validate the identity provider's JWT and map claims/groups to application roles.

Possible identity providers include:

* Microsoft Entra ID
* Okta
* Auth0
* Other OIDC-compatible providers

---

# 7. RBAC

The application stores a role for each user and includes the role in the JWT.

Example roles:

### Admin

Can be authorized to:

* Manage users
* Manage configuration
* Access operational metrics
* Perform administrative actions

### User

Can:

* Authenticate
* Use `/chat`

### Read-only

Can be authorized to:

* Access permitted reports
* View permitted data
* Cannot modify system configuration

The current implementation establishes the role information. Production administrative endpoints can add explicit role-based authorization dependencies.

---

# 8. Redis Caching

Redis is used to cache chat responses.

The question is normalized and hashed using SHA-256.

Cache key:

```text
chat:<sha256-hash>
```

Default TTL:

```text
300 seconds
```

Request flow:

```text
              /chat
                 |
                 v
            Redis Cache
              /     \
           HIT       MISS
            |          |
            v          v
         Return      LLM API
         response       |
                        v
                     Redis
                        |
                        v
                    Response
```

Caching reduces repeated LLM calls, token consumption, external provider dependency, and response latency for repeated questions.

---

# 9. Redis Rate Limiting

Redis is also used for distributed rate limiting.

Current application policy:

```text
30 requests / user / 60 seconds
```

Rate-limit key:

```text
rate_limit:<user_id>:<time_window>
```

When the limit is exceeded:

```text
HTTP 429 Too Many Requests
```

is returned.

Because the state is stored in Redis rather than application memory, the same rate-limit state can be shared across multiple API instances.

---

# 10. LLM Reliability

The application uses a primary and fallback LLM model.

The reliability flow is:

```text
              Primary LLM
                   |
             +-----+-----+
             |           |
          Success      Failure
             |           |
             v           v
           Return     Is failure
                      transient?
                         |
                  +------+------+
                  |             |
                 Yes            No
                  |             |
                  v             v
                Retry       Fallback
                  |
                  v
              Fallback
                  |
             +----+----+
             |         |
          Success    Failure
             |         |
             v         v
           Return     503
```

Transient failures include:

* Timeout
* HTTP 429
* HTTP 5xx

The implementation uses bounded retry behavior to avoid retry storms and excessive request latency.

---

# 11. Timeout Handling

Each LLM request has a bounded timeout.

If the primary model becomes slow:

```text
Primary LLM
    |
    | timeout
    v
Retry
    |
    | failure
    v
Fallback Model
```

If all configured models fail, the API returns:

```text
503 Service Unavailable
```

This prevents a slow external provider from indefinitely occupying API resources.

---

# 12. Error Handling

The API uses appropriate HTTP status codes.

| Situation                      | Response |
| ------------------------------ | -------: |
| Successful request             |      200 |
| Invalid credentials            |      401 |
| Missing/invalid authentication |      401 |
| Rate limit exceeded            |      429 |
| LLM service unavailable        |      503 |
| LLM timeout                    |      504 |
| Invalid request payload        |      422 |

---

# 13. Observability

Prometheus instrumentation provides visibility into:

* HTTP request count
* HTTP request latency
* LLM request count
* LLM request status
* LLM request latency
* Prompt token usage
* Completion token usage
* Cache hits
* Cache misses
* Rate-limit violations

Important metrics:

```text
llm_requests_total
llm_request_duration_seconds
llm_tokens_total
cache_hits_total
cache_misses_total
rate_limit_exceeded_total
```

Production alerts should monitor:

* High 5xx rate
* High 429 rate
* High p95/p99 latency
* LLM timeout rate
* LLM token consumption
* Redis availability
* PostgreSQL availability
* Queue depth
* API saturation

---

# 14. Docker

The complete application stack can run with Docker Compose.

Services:

```text
api
postgres
redis
```

Build:

```bash
docker compose build
```

Start:

```bash
docker compose up -d
```

Check:

```bash
docker compose ps
```

Logs:

```bash
docker compose logs -f api
```

Stop:

```bash
docker compose down
```

PostgreSQL and Redis use persistent Docker volumes.

The API container receives environment-specific configuration through environment variables.

---

# 15. Environment Configuration

Secrets are not hard-coded into the application.

Example:

```env
APP_NAME=AI Q&A Platform
APP_ENV=development

DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/aiqa
REDIS_URL=redis://redis:6379

JWT_SECRET=change-me
JWT_ALGORITHM=HS256

LLM_API_KEY=your-api-key
LLM_MODEL=your-model
LLM_FALLBACK_MODEL=your-fallback-model
```

The real `.env` file is excluded from Git.

In production, secrets should be stored in a managed secret manager rather than committed to source control or baked into Docker images.

---

# 16. Local Setup

Create a virtual environment:

```bash
python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create configuration:

```powershell
copy .env.example .env
```

Update `.env` with the required configuration.

Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Start the API:

```bash
uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Health:

```text
http://127.0.0.1:8000/health
```

Metrics:

```text
http://127.0.0.1:8000/metrics
```

---

# 17. Testing

The project contains automated tests covering:

* Root endpoint
* Authentication protection
* Successful chat
* Redis cache hit
* Rate limiting
* LLM failure handling
* Invalid question validation
* Maximum question length validation

Run:

```bash
pytest -v
```

Current result:

```text
8 passed
```

LLM calls are mocked during tests, so tests do not depend on external LLM availability.

---

# 18. Scaling Design

The API is designed to be stateless.

For the required 100 RPS baseline and occasional 500 RPS spikes, production deployment would use:

```text
Users
  |
  v
Load Balancer
  |
  +--------+--------+
  |        |        |
  v        v        v
API      API      API
  |        |        |
  +--------+--------+
           |
     +-----+-----+
     |           |
   Redis     PostgreSQL
     |
     v
Queue / LLM Gateway
     |
     v
LLM APIs
```

Detailed scaling decisions are documented in:

```text
docs/scaling.md
```

---

# 19. Migration Design

The migration plan addresses moving a Python LLM application from a single EC2 instance to a production architecture supporting approximately 10,000 users.

The design covers:

* Stateless API instances
* Load balancing
* Kubernetes/ECS
* Managed PostgreSQL
* Managed Redis
* Queue-based workload control
* LLM rate/concurrency limits
* Retries and timeouts
* Fallback providers
* Monitoring
* Secret management
* Minimal-downtime migration
* Rollback strategy

Detailed answer:

```text
docs/migration.md
```

---

# 20. Production Improvements

The assessment implementation is intentionally compact.

For a larger production environment, I would additionally consider:

* Kubernetes or ECS
* Kubernetes HPA
* Managed PostgreSQL
* Managed Redis
* Background queue such as SQS/RabbitMQ/Kafka
* LLM gateway
* Provider-specific rate limiting
* Global concurrency control
* Circuit breaker
* OpenTelemetry
* Grafana
* Structured logging
* Alembic migrations
* CI/CD
* Blue/green deployments
* Canary releases
* Automated rollback
* Container vulnerability scanning

These are architectural extensions rather than requirements for the local assessment environment.

---

# 21. Verification

Run:

```bash
docker compose build
docker compose up -d
docker compose ps
```

Verify:

```text
GET  /health
GET  /metrics
POST /auth/login
POST /chat
```

Run:

```bash
pytest -v
```

Expected:

```text
8 passed
```

---

