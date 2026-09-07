# Question 5 — Architecture and Migration

## Problem

The current application runs on a single EC2 server and supports approximately 10 users.

The expected user base is increasing to approximately 10,000 users.

The application also uses an external LLM API and occasionally becomes slow or crashes.

The objective is to migrate to a scalable architecture with minimal downtime.

---

# 1. Target Architecture

```text
                           Users
                             |
                             v
                     +---------------+
                     | Load Balancer |
                     | HTTPS / TLS   |
                     +-------+-------+
                             |
                +------------+------------+
                |            |            |
                v            v            v
             FastAPI      FastAPI      FastAPI
             Instance     Instance     Instance
                |            |            |
                +------------+------------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
           Redis                       PostgreSQL
              |
              +----------------+
              |                |
              v                v
           Cache           Rate Limit
              |
              v
         Queue / LLM Gateway
              |
        +-----+-----+
        |           |
        v           v
   Primary LLM   Fallback LLM
        |           |
        +-----+-----+
              |
          LLM APIs
```

A Kubernetes or ECS environment can host the FastAPI instances.

---

# 2. Step 1 — Make the API Stateless

The first migration step is to remove dependency on local EC2 state.

The API should not store:

* Sessions in local memory
* Cache in local memory
* Rate limits in local memory
* Persistent user data on the EC2 filesystem

Instead:

```text
PostgreSQL
    |
    +--> Persistent application data

Redis
    |
    +--> Cache
    +--> Rate limiting

FastAPI
    |
    +--> Stateless request processing
```

This makes it possible to run multiple API instances simultaneously.

---

# 3. Step 2 — Containerize the Application

Package the application into a Docker image.

The image contains the application and its Python dependencies.

Environment-specific values should be injected at runtime.

The Docker image should not contain:

* LLM API keys
* JWT secrets
* Database passwords
* Production configuration secrets

This project already provides a Dockerfile and Docker Compose configuration for containerized deployment.

---

# 4. Step 3 — Introduce a Load Balancer

Instead of users connecting directly to one EC2 instance:

```text
Users
  |
  v
EC2
```

move to:

```text
Users
  |
  v
Load Balancer
  |
  +---- FastAPI #1
  +---- FastAPI #2
  +---- FastAPI #3
```

The load balancer should perform health checks.

If an API instance fails:

```text
API #2
   |
   v
Unhealthy
   |
   v
Remove from traffic
```

Other instances continue serving users.

---

# 5. Step 4 — Move PostgreSQL to Managed Infrastructure

The database should not remain tied to the application EC2 server.

Move PostgreSQL to a managed database service.

The managed database should provide:

* Automated backups
* High availability
* Monitoring
* Recovery options
* Connection management

Application data such as users and roles remains persistent outside the API containers.

---

# 6. Step 5 — Move Redis to Managed Infrastructure

Redis should also become independent of the API instances.

Use managed Redis with:

* Replication
* High availability
* Automatic failover
* Monitoring
* Appropriate security controls

Redis provides:

```text
Cache
Rate limiting
```

This shared Redis state works across all FastAPI replicas.

---

# 7. Step 6 — Handle LLM API Limits

The LLM provider is likely to become a major bottleneck before the FastAPI layer.

LLM providers can impose:

* RPM limits
* TPM limits
* Concurrent request limits
* Account/provider quotas

Therefore, I would introduce an LLM gateway or service layer:

```text
FastAPI
   |
   v
LLM Gateway
   |
   +--> Rate limiter
   |
   +--> Concurrency limiter
   |
   +--> Model routing
   |
   v
LLM Provider
```

This prevents every FastAPI instance from independently consuming the provider quota.

---

# 8. Step 7 — Handle Slow LLM Requests

Each LLM request should have a bounded timeout.

Example:

```text
FastAPI
   |
   v
Primary LLM
   |
   | timeout
   v
Retry
   |
   | still failing
   v
Fallback LLM
```

The current implementation uses a bounded timeout and fallback strategy.

The retry policy should only retry transient failures such as:

* Timeout
* HTTP 429
* HTTP 5xx

Permanent errors should not cause repeated retries.

---

# 9. Step 8 — Use Queues for Long-Running Workloads

Not every LLM task needs to block the HTTP request.

For long-running workloads:

```text
Client
  |
  v
FastAPI
  |
  v
Queue
  |
  v
Worker
  |
  v
LLM Gateway
```

The client can receive a job ID and retrieve the result later.

This is useful for:

* Long document processing
* Batch generation
* Large summarization jobs
* Embedding generation
* RAG ingestion
* Other asynchronous workloads

For normal short Q&A, synchronous processing can remain simpler.

---

# 10. Step 9 — Scaling to 10,000 Users

The API layer can be horizontally scaled:

```text
                 Load Balancer
                      |
        +-------------+-------------+
        |             |             |
      API #1        API #2        API #N
        |             |             |
        +-------------+-------------+
                      |
              +-------+-------+
              |               |
            Redis          PostgreSQL
```

Kubernetes HPA can automatically increase API replicas during sustained traffic.

Scaling signals could include:

* CPU
* Memory
* Request concurrency
* p95 latency
* Queue depth

The exact replica count should be determined through load testing.

---

# 11. Step 10 — Monitoring

The production environment should have centralized observability.

### API metrics

```text
Requests/sec
p50 latency
p95 latency
p99 latency
4xx rate
5xx rate
```

### LLM metrics

```text
LLM requests
LLM latency
LLM timeouts
LLM 429 responses
Token usage
Fallback frequency
```

### Infrastructure metrics

```text
CPU
Memory
Database connections
Redis memory
Redis availability
Queue depth
```

Prometheus can collect the metrics and Grafana can provide dashboards.

---

# 12. Failure Handling

## FastAPI instance failure

Load balancer removes the unhealthy instance.

Other instances continue serving requests.

---

## Redis failure

Caching becomes unavailable.

The application can degrade to direct LLM calls where appropriate.

Rate limiting requires a deliberate production policy:

* Fail closed
* Fail open
* Emergency local limiter

For a public API, protection against uncontrolled traffic should be prioritized.

---

## PostgreSQL failure

Database operations fail safely and health checks report the database as unhealthy.

High availability and backups should be provided by the managed database platform.

---

## LLM provider failure

Use:

```text
Primary provider
      |
      v
Retry transient error
      |
      v
Secondary model/provider
      |
      v
503 if all providers fail
```

A circuit breaker can prevent repeated calls to a known failing provider.

---

# 13. Minimal-Downtime Migration

I would use a staged migration rather than shutting down the existing EC2 application.

## Phase 1 — Prepare

Build the Docker image and provision:

* Managed PostgreSQL
* Managed Redis
* New application environment
* Secret management
* Load balancer

---

## Phase 2 — Database Migration

Perform an initial data migration from the existing PostgreSQL database.

Then continuously synchronize changes if supported by the chosen migration strategy.

Validate:

* Row counts
* User records
* Roles
* Application queries

---

## Phase 3 — Deploy New Application

Deploy the containerized FastAPI application without sending production traffic yet.

Run health checks:

```text
GET /health
```

Test:

```text
POST /auth/login
POST /chat
GET /metrics
```

---

## Phase 4 — Gradual Traffic Migration

Instead of switching 100% of traffic immediately:

```text
Old EC2
   |
   | 90%
   |
   v

New Platform
   |
   | 10%
```

Monitor the new environment.

If healthy:

```text
Old EC2      50%
New Platform 50%
```

Then:

```text
Old EC2      10%
New Platform 90%
```

Finally:

```text
Old EC2       0%
New Platform 100%
```

This can be implemented using load-balancer routing, weighted traffic, blue/green deployment, or canary deployment.

---

# 14. Database Cutover

For a minimal-downtime database migration:

1. Provision the target managed PostgreSQL.
2. Perform the initial data copy.
3. Replicate/synchronize changes.
4. Validate data consistency.
5. Make the application compatible with both old and new schemas.
6. Temporarily control writes if required.
7. Apply the final synchronization.
8. Switch the application connection string.
9. Validate application behavior.
10. Keep the old database available for rollback.

The old database should not be deleted immediately.

---

# 15. Backward-Compatible Database Changes

Database schema changes should follow an expand-and-contract approach.

```text
Old Application
      |
      v
Add new compatible schema
      |
      v
Deploy new application
      |
      v
Migrate data
      |
      v
Switch traffic
      |
      v
Remove old schema later
```

This avoids requiring the application and database to change simultaneously.

---

# 16. Secret Management

Secrets should never be stored in:

* Git
* Docker images
* Source code
* Client applications

Production secrets should be stored in a managed secret manager.

Examples include:

* AWS Secrets Manager
* AWS Systems Manager Parameter Store
* Kubernetes Secrets with appropriate encryption and access controls
* Cloud provider secret-management services

Secrets include:

```text
LLM API key
JWT signing secret
Database credentials
Redis credentials
```

Applications should receive secrets at runtime.

---

# 17. Rollback Strategy

The migration should have a clear rollback path.

If the new platform experiences:

* High error rate
* High latency
* Database problems
* LLM integration issues

traffic can be shifted back to the old EC2 environment.

```text
                 Load Balancer
                      |
              +-------+-------+
              |               |
          New Platform     Old EC2
              |
           Problem
              |
              v
        Shift traffic
        back to EC2
```

The old environment should remain available until the new platform is stable.

---

# 18. Trade-offs

### Kubernetes

**Advantages:**

* Automatic scaling
* Self-healing
* Deployment strategies
* Service discovery

**Trade-off:**

* Higher operational complexity

For a smaller team, ECS or another managed container platform may be simpler.

---

### Managed PostgreSQL

**Advantages:**

* Backups
* High availability
* Reduced operational work

**Trade-off:**

* Higher infrastructure cost

---

### Redis

**Advantages:**

* Fast caching
* Distributed rate limiting
* Shared state across replicas

**Trade-off:**

* Additional infrastructure dependency

---

### Queue

**Advantages:**

* Absorbs traffic spikes
* Controls LLM concurrency
* Supports asynchronous work

**Trade-off:**

* Adds complexity
* Can increase latency for synchronous workloads

---

### Multiple LLM providers

**Advantages:**

* Better availability
* Provider outage protection
* Flexible model routing

**Trade-off:**

* More integration complexity
* Different model quality and pricing
* Different token limits

---

# Conclusion

The migration should transform the single EC2 application into a stateless, horizontally scalable service:

```text
Users
  |
  v
Load Balancer
  |
  v
Kubernetes / ECS
  |
  +---- FastAPI replicas
  |
  +---- Redis
  |
  +---- Queue / LLM Gateway
  |
  +---- Managed PostgreSQL
  |
  v
LLM Providers
```

The migration should be gradual rather than a single large cutover. Externalizing state, introducing health checks and load balancing, migrating the database carefully, using managed secrets, and maintaining the old EC2 environment for rollback provide a practical path to approximately 10,000 users with minimal downtime.
