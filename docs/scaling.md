# Question 4 — Scaling Scenario

## Problem

The application receives approximately:

* 100 requests/second normally
* Up to 500 requests/second during traffic spikes

The goal is to support these spikes without allowing the LLM provider, database, Redis, or API layer to become unstable.

The proposed architecture is:

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
      +------+------+
      |             |
    Cache         Rate Limit
      |
      v
 Request Queue
      |
      v
 LLM Gateway
      |
      +----------------+
      |                |
      v                v
 Primary LLM      Fallback LLM
```

---

# 1. Horizontal Scaling

FastAPI instances should remain stateless.

Instead of running one API process:

```text
API #1
```

the production environment can run:

```text
API #1
API #2
API #3
...
API #N
```

A load balancer distributes requests between healthy instances.

This allows the API layer to scale horizontally without requiring users to stay connected to a particular server.

For an initial 100 RPS deployment, I would start with multiple replicas and determine the required replica count using load testing.

I would not assume that a fixed number of replicas can always handle a specific RPS because actual capacity depends on:

* CPU
* Memory
* Request duration
* Concurrent LLM calls
* Cache hit rate
* Network latency

---

# 2. Load Balancing

A load balancer sits in front of the FastAPI instances:

```text
Users
  |
  v
Load Balancer
  |
  +---- API #1
  |
  +---- API #2
  |
  +---- API #3
```

The load balancer should perform health checks.

Unhealthy instances should automatically stop receiving traffic.

This prevents one failed API instance from affecting all users.

---

# 3. Kubernetes HPA

In a Kubernetes deployment, the API can be managed using a Horizontal Pod Autoscaler.

Conceptually:

```text
Normal traffic
     |
     v
3 API replicas
     |
Traffic increases
     |
     v
HPA detects sustained load
     |
     v
Increase replicas
     |
     v
5 → 10+ replicas
```

HPA can use signals such as:

* CPU utilization
* Memory utilization
* Request concurrency
* Custom metrics
* Queue depth

For this application, CPU alone may not be sufficient because LLM requests are often network-bound.

Therefore, request concurrency, latency, and queue depth are useful additional signals.

---

# 4. Redis

Redis has two major roles.

## Cache

Repeated questions can be served from Redis without calling the LLM.

```text
Question
   |
   v
Redis
   |
   +---- HIT ----> Response
   |
   +---- MISS ---> LLM
```

This reduces:

* LLM requests
* Token consumption
* External provider load
* Response latency

## Distributed Rate Limiting

Redis also stores rate-limit counters.

Because Redis is shared between API instances:

```text
API #1 ─┐
API #2 ─┼──> Redis rate limit
API #3 ─┘
```

all instances enforce the same user-level limit.

---

# 5. Background Queues

At 500 RPS, directly sending every request to the LLM can overload the provider.

LLM providers commonly enforce:

* Requests per minute
* Tokens per minute
* Concurrent request limits

A queue can absorb traffic bursts:

```text
API
 |
 +---- Redis Cache
 |
 +---- Request Queue
          |
          v
      LLM Workers
          |
          v
      LLM Gateway
          |
          v
       Provider
```

The queue allows the system to control how many LLM requests execute simultaneously.

For interactive chat, synchronous responses may still be preferred when the provider can handle the load. Queues are especially useful for long-running, asynchronous, or burst-heavy workloads.

---

# 6. Rate Limiting

There should be multiple levels of rate limiting.

## Per-user limit

Protects individual users from excessive requests.

Example:

```text
30 requests / user / minute
```

This is already implemented using Redis.

## Global application limit

Protects the whole application from unexpected traffic.

## Provider-specific limit

Protects the LLM provider quota.

For example:

```text
Application
    |
    v
Provider concurrency = maximum allowed
```

Requests beyond the safe provider concurrency can wait in a queue or receive a controlled response.

---

# 7. LLM API Limits

LLM providers can enforce:

### RPM

Requests per minute.

### TPM

Tokens per minute.

### Concurrency

Number of simultaneous requests.

A 500 RPS application cannot assume that the LLM provider can process 500 LLM calls every second.

Therefore, the architecture should separate:

```text
API traffic
```

from:

```text
LLM traffic
```

using caching, queues, rate limits, and concurrency control.

---

# 8. Concurrent Requests

FastAPI supports asynchronous request handling.

The API can therefore handle many concurrent network operations without blocking a worker for every waiting network operation.

However, asynchronous FastAPI does not remove external LLM concurrency limits.

A provider concurrency limiter should therefore be introduced in production.

Example:

```text
500 incoming requests
        |
        v
FastAPI
        |
        v
Concurrency limiter
        |
        +---- Allowed ----> LLM
        |
        +---- Waiting -----> Queue
```

---

# 9. Failure Recovery

LLM failures should not crash the API.

The implementation uses:

```text
Primary LLM
     |
     v
Timeout
     |
     v
Bounded retry
     |
     v
Fallback model
     |
     v
503 if all fail
```

Transient errors such as:

* Timeout
* HTTP 429
* HTTP 5xx

can be retried.

Permanent errors should not be retried indefinitely.

---

# 10. Graceful Degradation

The system should continue operating partially when dependencies fail.

### Redis failure

Caching may be temporarily unavailable.

The API can continue to the LLM where appropriate.

For rate limiting, production policy should be explicitly chosen between fail-open, fail-closed, or an emergency local limiter.

### LLM failure

Use fallback models/providers.

If all providers fail:

```text
503 Service Unavailable
```

### PostgreSQL failure

Authentication and persistent operations should fail safely, while health checks report the dependency as unhealthy.

---

# 11. Monitoring

Prometheus should monitor:

```text
API RPS
HTTP latency
p50 latency
p95 latency
p99 latency
HTTP 4xx
HTTP 5xx

LLM requests
LLM latency
LLM timeouts
LLM 429s
LLM token usage

Redis cache hits
Redis cache misses
Rate-limit violations

Queue depth
Database connections
CPU
Memory
```

Important alerts:

```text
High p95/p99 latency
High 5xx rate
High LLM timeout rate
High LLM 429 rate
High queue depth
Redis unavailable
PostgreSQL unavailable
Unexpected token consumption
```

---

# 12. Why This Architecture

The key design principle is to avoid treating the LLM as an unlimited synchronous dependency.

The API layer can scale horizontally:

```text
100 RPS → multiple FastAPI instances
```

but the LLM layer may scale differently because of provider quotas.

Therefore:

```text
FastAPI scaling
        +
Redis caching
        +
Rate limiting
        +
Queueing
        +
LLM concurrency control
        +
Retry/fallback
        +
Monitoring
```

together provide a safer architecture for 100 RPS with occasional 500 RPS spikes.

---

# 13. Trade-offs

### More FastAPI instances

**Benefit:** More API concurrency.

**Trade-off:** Higher infrastructure cost.

### Redis caching

**Benefit:** Lower LLM cost and latency.

**Trade-off:** Cached answers may become stale.

### Queue

**Benefit:** Protects LLM provider during bursts.

**Trade-off:** Can increase response latency and introduces asynchronous complexity.

### Multiple LLM providers

**Benefit:** Better availability and resilience.

**Trade-off:** More configuration, cost management, and response consistency concerns.

### Kubernetes HPA

**Benefit:** Automatic scaling.

**Trade-off:** Additional operational complexity compared with a small Docker Compose deployment.

---

# Conclusion

For the 100 → 500 RPS scenario, I would keep FastAPI stateless and scale it horizontally behind a load balancer. Redis provides shared caching and distributed rate limiting. A queue and LLM gateway control provider concurrency and absorb bursts. HPA scales API replicas based on sustained load, while timeout, bounded retry, fallback, and monitoring provide failure recovery and graceful degradation.
