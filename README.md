# URLForge

> A scalable, production-grade URL-shortening and analytics service built with Python 3.11, FastAPI, Redis, and PostgreSQL. Designed specifically as an educational Computer Science and backend systems engineering portfolio project.

---

## 1. Project Overview

URLForge goes beyond a basic URL redirector to demonstrate real-world backend engineering concepts:
* **High-Throughput ASGI Architecture:** Asynchronous request handling powered by FastAPI and Uvicorn.
* **Cache-Aside Caching:** Sub-millisecond redirect lookups using Redis with automated PostgreSQL fallback.
* **Concurrency & Race Condition Control:** Database-level `UNIQUE` constraints and retry backoffs.
* **Distributed Rate Limiting:** Redis-backed rate limiting defending against link spam and denial of service.
* **Idempotency Support:** `Idempotency-Key` headers preventing accidental duplicate creation upon network retries.
* **Privacy-First Analytics:** Salted hashing for client identity; user-agent and referrer tracking.
* **Deep Observability:** Structured JSON logging, Prometheus metrics, and automated health checks.

---

## 2. Technology Stack

* **Language:** Python 3.11+
* **Framework:** FastAPI (ASGI on Starlette)
* **ASGI Server:** Uvicorn (uvloop & httptools)
* **Configuration:** Pydantic 2.x & Pydantic Settings (12-Factor principles)
* **Database:** PostgreSQL (with SQLAlchemy 2.x & asyncpg)
* **Migrations:** Alembic
* **Cache & Rate Limiting:** Redis
* **Testing:** Pytest, pytest-asyncio, HTTPX
* **Containerization:** Docker & Docker Compose

---

## 3. Project Directory Structure

```text
URLForge/
├── app/
│   ├── __init__.py           # Application package
│   ├── main.py               # FastAPI application entrypoint & middleware
│   ├── config.py             # 12-factor Pydantic environment settings
│   ├── database.py           # Async SQLAlchemy engine & session dependency
│   ├── models.py             # SQLAlchemy ORM declarative models
│   ├── schemas.py            # Pydantic request/response validation schemas
│   ├── dependencies.py       # FastAPI dependency injection providers
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py         # /health monitoring probe
│   │   ├── urls.py           # URL creation, redirect, and deletion
│   │   └── analytics.py      # Click metrics and traffic statistics
│   ├── services/
│   │   ├── __init__.py
│   │   ├── url_service.py    # URL generation and persistence logic
│   │   ├── cache_service.py  # Cache-aside Redis read/write/invalidation
│   │   ├── analytics_service.py # Event logging and click aggregation
│   │   └── rate_limit_service.py # Distributed rate limiting
│   └── utils/
│       ├── __init__.py
│       ├── short_code.py     # Base62 encoding and decoding
│       └── security.py       # Hashing and privacy anonymization
├── tests/
│   ├── __init__.py
│   ├── test_health.py        # Health and root probe tests
│   ├── test_urls.py          # URL creation and validation tests
│   ├── test_redirect.py      # Redirect semantics and cache hit tests
│   ├── test_analytics.py     # Click tracking and stats tests
│   └── test_rate_limit.py    # Rate limiter concurrency tests
├── docs/
│   ├── architecture.md       # Full system design and Mermaid diagrams
│   ├── decisions.md          # Architecture Decision Records (ADRs)
│   ├── capacity.md           # Capacity math and load projections
│   └── interview.md          # 50+ backend interview questions and answers
├── Dockerfile                # Production container configuration
├── docker-compose.yml        # Multi-service local composition (App, PG, Redis)
├── requirements.txt          # Python dependencies
├── pytest.ini               # Test harness configuration
├── .env.example              # Environment variables template
└── LICENSE                   # MIT License
```

---

## 4. Getting Started

### Local Setup (Virtual Environment)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/URLForge.git
   cd URLForge
   ```

2. **Create and activate the virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

5. **Run the FastAPI server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Verify the server:**
   ```bash
   curl -i http://localhost:8000/health
   ```

---

## 5. Running Tests

Run the complete test suite using Pytest:

```bash
pytest -v
```

To run with coverage reporting:
```bash
pytest --cov=app tests/
```

---

## 6. Architecture & Implementation Roadmap

| Phase | Milestone | Status | Description |
|---|---|---|---|
| **Phase 1** | **FastAPI Core Skeleton** | **Completed** | Minimal ASGI app, GET /, GET /health, Pydantic settings, Pytest suite |
| **Phase 2** | **URL Creation (POST /api/v1/urls)** | **Completed** | Pydantic URL validation, schema definitions, service layer abstraction |
| **Phase 3** | **PostgreSQL & SQLAlchemy 2.x** | **Completed** | Async engine, connection pool, Alembic migrations, constraints & indexes |
| **Phase 4** | **HTTP Redirect (GET /{short_code})** | **Completed** | HTTP 307 vs 301/302 semantics, path routing, lookup performance |
| **Phase 5** | **Short Code Generation & Base62** | **Completed** | Base62 bi-directional encoding, collision detection, unique constraints |
| **Phase 6** | **Redis Caching (Cache-Aside)** | **Completed** | Cache get/set/delete, TTL, hit/miss metrics, graceful fallback on outage |
| **Phase 7** | **Analytics & Click Tracking** | **Completed** | Click counts, timestamps, user-agent parsing, referrer, privacy-first |
| **Phase 8** | **Redis-Backed Rate Limiting** | **Completed** | Token bucket/sliding window, concurrency control, 429 Too Many Requests |
| **Phase 9** | **Idempotency (Idempotency-Key)** | **Completed** | Prevent duplicate creation on network retries, key replay & caching |
| **Phase 10** | **Comprehensive Test Suite** | **Completed** | Unit, integration, and concurrency race-condition tests with Pytest (44 tests) |
| **Phase 11** | **Docker & Compose** | **Completed** | Multi-stage Dockerfile, docker-compose.yml (FastAPI, Postgres, Redis) |
| **Phase 12** | **Observability & Metrics** | **Completed** | Structured JSON logging, correlation IDs, Prometheus metrics exporter |
| **Phase 13** | **Performance Benchmarks** | **Completed** | Locust load testing, P50/P95/P99 latency, cache hit ratio comparisons |
| **Phase 14** | **Chaos & Failure Testing** | **Completed** | Simulated Redis outage, DB connection drop, graceful degradation |
| **Phase 15** | **System Design & Capacity Planning** | **Completed** | 100M URLs/month math, sharding, replication, interview guide |

---

## 7. License

Licensed under the [MIT License](LICENSE).
