# URLForge Architecture Decision Records (ADRs)

This document records the architectural choices, trade-offs, and design rationale for the URLForge service.

---

## ADR-001: Choice of Primary Database (PostgreSQL)

* **Status:** Accepted
* **Context:** URLForge requires persistent storage for URL mappings, expiration dates, ownership metadata, and analytical summaries. URL mappings require strict ACID compliance, data integrity guarantees, and low write collision rates.
* **Decision:** Use PostgreSQL as the relational primary datastore, accessed asynchronously via SQLAlchemy 2.x and asyncpg.
* **Alternatives Considered:**
  * *MongoDB / Document DBs:* Schemaless nature makes enforcing strict relational constraints and indexing consistency harder. Lack of mature transactional multi-table integrity at high velocity.
  * *DynamoDB / Cassandra:* Excellent for simple key-value reads at hyper-scale, but complex indexing, analytical aggregation, and local development overhead are higher for this phase.
* **Trade-offs:**
  * *Pros:* Native B-tree unique index support, robust foreign key relationships, mature Alembic migration tooling, reliable WAL (Write-Ahead Logging), and battle-tested consistency.
  * *Cons:* Requires vertical scaling or explicit read replicas/sharding as traffic grows beyond single-node write throughput limits.

---

## ADR-002: Choice of In-Memory Cache (Redis)

* **Status:** Accepted
* **Context:** URL shorteners have an extreme read-to-write ratio (typically 10:1 to 100:1). Querying PostgreSQL on every redirect introduces latency (5–20ms per query) and exhausts database connection pools.
* **Decision:** Introduce Redis as an in-memory caching and rate-limiting tier.
* **Alternatives Considered:**
  * *Memcached:* Simple and fast key-value store, but lacks data structures (hashes, sorted sets), atomic increment scripts, and pub/sub capabilities.
  * *In-process Python Memory (lru_cache / dict):* Memory is isolated per process. In multi-worker or multi-container deployments, cache state is fragmented and rate limiting cannot be coordinated.
* **Trade-offs:**
  * *Pros:* Sub-millisecond lookup latency (~0.5ms), atomic Lua scripting for rate limiting and sliding windows, built-in key TTL expiration.
  * *Cons:* Additional distributed dependency to monitor and maintain. Cache invalidation logic must be handled carefully.

---

## ADR-003: Short Code Encoding Algorithm (Base62)

* **Status:** Accepted
* **Context:** Original URLs need to be mapped to concise, user-friendly alphanumeric tokens that are safe in URLs and human readable.
* **Decision:** Use Base62 encoding (`[0-9a-zA-Z]`), generating 7-character strings yielding $62^7 \approx 3.52 \times 10^{12}$ unique combinations.
* **Alternatives Considered:**
  * *Base64:* Includes `+` and `/` (or `-` and `_` in URL-safe Base64), which can cause URL delimiter collisions or awkward shell escaping.
  * *MD5 / SHA-256 Truncation:* Produces hexadecimal strings (`0-9a-f`, only 16 characters per position), requiring much longer strings for the same collision resistance.
  * *UUID v4:* 36 characters long, defeating the core purpose of a short URL.
* **Trade-offs:**
  * *Pros:* URL-safe without escaping, high information density (6 bits per character), compact representations.
  * *Cons:* Case sensitivity must be preserved across client environments (some non-compliant systems treat URLs as case-insensitive).

---

## ADR-004: Caching Strategy (Cache-Aside / Lazy Loading)

* **Status:** Accepted
* **Context:** We need to keep Redis synchronized with PostgreSQL while maintaining resilience against cache crashes.
* **Decision:** Implement the Cache-Aside pattern for redirects:
  1. Check Redis for `short_code`.
  2. If hit: return immediately.
  3. If miss: query PostgreSQL, store result in Redis with TTL, return URL.
  4. On URL deletion or expiration: explicitly evict/delete from Redis.
* **Alternatives Considered:**
  * *Write-Through Cache:* Writes go to Redis first, which synchronously updates Postgres. Increases write latency and risks data loss if cache writes fail.
  * *Write-Behind (Write-Back) Cache:* Asynchronous queue to DB. High throughput but risks data loss during crash before flush.
* **Trade-offs:**
  * *Pros:* Only actively accessed URLs consume cache RAM. If Redis crashes, requests degrade to PostgreSQL without total outage.
  * *Cons:* Cache misses experience latency penalty (cache check + database query + cache write). Potential stale data if database is updated out-of-band without eviction.

---

## ADR-005: Enforcement of Uniqueness via Database Constraints

* **Status:** Accepted
* **Context:** In concurrent multi-process environments, two requests could generate the same short code at the exact same millisecond.
* **Decision:** Add a `UNIQUE` constraint and B-tree index on `short_code` in PostgreSQL and rely on database-level constraint validation rather than application-level `SELECT ... WHERE` checks.
* **Alternatives Considered:**
  * *Application-Level Pre-Check (`SELECT EXISTS`):* Prone to Time-of-Check to Time-of-Use (TOCTOU) race conditions.
  * *Distributed Locks (Redlock):* Adds latency and failure complexity to the write path.
* **Trade-offs:**
  * *Pros:* ACID-guaranteed uniqueness under extreme concurrency.
  * *Cons:* Application code must catch `IntegrityError` and implement retry logic with exponential backoff.

---

## ADR-006: Distributed Rate Limiting via Redis

* **Status:** Accepted
* **Context:** Public URL shorteners are frequent targets for abuse, denial-of-service, and malicious link spam.
* **Decision:** Implement Redis-backed token bucket / sliding window rate limiting keyed by client identity (IP or API key).
* **Alternatives Considered:**
  * *In-Memory Rate Limiting (e.g. slowapi with MemoryStorage):* Fails completely when scaling horizontally across multiple container instances or load-balanced replicas.
* **Trade-offs:**
  * *Pros:* Globally consistent rate limit accounting across all API worker processes.
  * *Cons:* Adds one network roundtrip to Redis per request on rate-limited endpoints.

---

## ADR-007: Stateless API Servers

* **Status:** Accepted
* **Context:** The system must scale horizontally behind a load balancer as traffic increases.
* **Decision:** Keep all FastAPI application instances strictly stateless. No sticky sessions, no in-memory user states, and no local file dependencies.
* **Alternatives Considered:**
  * *Stateful instances with session affinity:* Restricts load balancing flexibility and complicates auto-scaling and zero-downtime rolling deploys.
* **Trade-offs:**
  * *Pros:* Trivial horizontal scaling (spin up 10 instances in Cloud Run or Kubernetes without state sync issues).
  * *Cons:* All state must reside in external datastores (PostgreSQL, Redis).
