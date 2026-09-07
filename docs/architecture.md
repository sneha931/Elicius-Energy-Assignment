# Architecture

## High-Level Architecture

```text
                         ┌──────────────────────┐
                         │       Client         │
                         │  Web / Mobile / API  │
                         └──────────┬───────────┘
                                    │
                                    │ HTTPS
                                    ▼
                         ┌──────────────────────┐
                         │    Load Balancer     │
                         │   (Production)       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ FastAPI  │    │ FastAPI  │    │ FastAPI  │
              │ Instance │    │ Instance │    │ Instance │
              │    #1    │    │    #2    │    │    #N    │
              └────┬─────┘    └────┬─────┘    └────┬─────┘
                   │               │               │
                   └───────────────┼───────────────┘
                                   │
                 ┌─────────────────┼──────────────────┐
                 │                 │                  │
                 ▼                 ▼                  ▼
          ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
          │    Redis    │   │ PostgreSQL  │   │ LLM Provider │
          │             │   │             │   │  OpenRouter  │
          │ Cache       │   │ Users       │   │              │
          │ Rate Limit  │   │ Auth Data   │   │ Primary      │
          └─────────────┘   └─────────────┘   │ Fallback     │
                                               └──────────────┘

                         ┌──────────────────────┐
                         │     Prometheus       │
                         │       Metrics        │
                         └──────────────────────┘