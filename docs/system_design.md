# URLForge - System Design & Capacity Planning

This document presents the end-to-end System Design and Capacity Planning for **URLForge**, an enterprise-grade, distributed URL Shortener and Analytics Platform engineered for high throughput, sub-5ms redirect latency, and continuous 99.99% availability.

---

## 1. Requirements & System Scope

### 1.1 Functional Requirements
1. **URL Shortening (Write Path)**:
   - Input: Long URL (up to 2048 characters) and optional custom alias.
   - Output: Compact 7-character Base62 short URL (e.g., `https://urlforge.io/7xK9q2L`).
   - Optional expiration timestamp (TTL).
   - Idempotent request handling (`Idempotency-Key` header).
2. **URL Redirection (Read Path)**:
   - Input: Short code HTTP request.
   - Output: HTTP 307 (Temporary Redirect) to original destination URL with sub-5 millisecond response time.
3. **Click Tracking & Analytics**:
   - Asynchronous event capture: IP hash (privacy-preserving SHA-256), Referer, User-Agent classification (device/browser), and timestamp.
   - Aggregated metrics API querying total clicks, unique visitors, device breakdown, and daily timeseries.
4. **Rate Limiting & Abuse Prevention**:
   - Sliding window rate limiting per client IP to prevent brute-force generation and denial-of-service.

### 1.2 Non-Functional Requirements
- **Ultra-Low Latency**: $P_{99} < 10\text{ms}$ and $P_{50} < 2\text{ms}$ for read redirects.
- **High Availability (HA)**: 99.99% uptime (~52.6 minutes allowed downtime/year). Redirection service must never fail even during database degradation.
- **High Durability**: Zero data loss for persisted short codes.
- **Collision Resistance**: Mathematical guarantee against duplicate code assignment across concurrent write threads.

---

## 2. Back-of-the-Envelope Capacity Estimation

### 2.1 Traffic Projections
URL shortening services exhibit an extreme **read-heavy workload** with an estimated read-to-write ratio of **100:1**.

* **New Short URLs (Writes)**:
  * 100 Million new URLs created per month.
  * Writes per second:
    $$\text{Write QPS} = \frac{100,000,000}{30 \times 24 \times 3600 \text{ s}} \approx 38.6 \text{ requests/sec}$$
  * Peak Writes per second ($3\times$ multiplier): $\approx 120 \text{ writes/sec}$.

* **URL Redirections (Reads)**:
  * 10 Billion redirects served per month.
  * Reads per second:
    $$\text{Read QPS} = \frac{10,000,000,000}{30 \times 24 \times 3600 \text{ s}} \approx 3,858 \text{ requests/sec}$$
  * Peak Reads per second ($4\times$ multiplier during peak global traffic): $\approx 15,500 \text{ reads/sec}$.

---

### 2.2 Short Code Permutation Space (Base62)
Using alphanumeric characters `[0-9a-zA-Z]` (62 unique characters):
$$\text{Total Combinations for length } L = 62^L$$

| Length ($L$) | Total Combinations | Sufficiency at 100M URLs/Month |
|---|---|---|
| 5 | $62^5 \approx 916 \text{ Million}$ | Depleted in ~9 months |
| 6 | $62^6 \approx 56.8 \text{ Billion}$ | Lasts ~47 years |
| **7** | $\mathbf{62^7 \approx 3.52 \text{ Trillion}}$ | **Lasts ~2,900 years (Selected standard)** |
| 8 | $62^8 \approx 218 \text{ Trillion}$ | Hyperscale reserved |

**Selected Encoding**: 7 characters yields **3,521,614,606,208** distinct addresses, guaranteeing negligible collision risk under cryptographic random or counter-based Base62 generation.

---

### 2.3 Storage Capacity Estimation (5-Year Horizon)

#### PostgreSQL URL Record Sizing:
* `id` (UUIDv4): 16 bytes
* `short_code` (VARCHAR(16)): 16 bytes
* `original_url` (VARCHAR(2048), average 180 bytes): ~180 bytes
* `created_at` (TIMESTAMPTZ): 8 bytes
* `expires_at` (TIMESTAMPTZ, nullable): 8 bytes
* `click_count` (BIGINT): 8 bytes
* `last_accessed_at` (TIMESTAMPTZ): 8 bytes
* Row Header & B-Tree index overhead: ~150 bytes
* **Total per URL row**: $\approx 400\text{ bytes}$

#### Storage Growth:
* **Monthly URL Storage**: $100 \times 10^6 \times 400 \text{ bytes} \approx 40 \text{ GB / month}$.
* **5-Year Cumulative URL Storage**:
  $$40 \text{ GB/month} \times 12 \times 5 = \mathbf{2.4 \text{ TB}}$$
  *Easily fits within a standard managed RDS/Aurora PostgreSQL cluster with room for replicas.*

#### Click Events Storage (Analytics):
* Total events per month: 10 Billion
* Per click event (event_id, url_id, timestamp, ip_hash, user_agent, referer): ~120 bytes
* Monthly event storage: $10 \times 10^9 \times 120 \text{ bytes} \approx 1.2 \text{ TB / month}$.
* *Architectural Note*: Raw click stream data is ingested asynchronously into Kafka and long-term analytical columnar storage (ClickHouse or Snowflake/BigQuery) with a 90-day retention in hot PostgreSQL.

---

### 2.4 In-Memory Cache Sizing (Redis)
Applying the **80/20 Pareto Principle**: **20% of URLs generate 80% of all redirect traffic**.
* Daily total redirect requests: $\approx 330 \text{ Million reads/day}$.
* Active unique URLs requested per day: $\approx 20\% \text{ of 100M} = 20 \text{ Million URLs}$.
* Memory required per cached key (`url:<short_code>` -> `destination_url`):
  * Key: `url:7xK9q2L` (11 bytes)
  * Value: `https://example.com/...` (180 bytes)
  * Redis dict entry overhead: ~100 bytes
  * Total memory per key: $\approx 300 \text{ bytes}$
* **Total Redis Memory**:
  $$20,000,000 \times 300 \text{ bytes} \approx \mathbf{6.0 \text{ GB RAM}}$$
* Adding a $3\times$ safety factor for Rate Limiting Sliding Windows, Idempotency keys, and Redis memory fragmentation:
  $$\text{Recommended Redis Cluster Capacity} = \mathbf{24 \text{ GB to 32 GB RAM}}$$
  *(A 3-node Redis cluster with 16GB per node provides full redundancy and sub-millisecond cache latency).*

---

### 2.5 Network Bandwidth Estimation
* **Write Ingress**:
  $$38.6 \text{ writes/sec} \times 500 \text{ bytes} \approx 19.3 \text{ KB/sec} \approx 0.15 \text{ Mbps}$$
* **Read Egress (Redirects)**:
  $$3,858 \text{ reads/sec} \times 500 \text{ bytes} \approx 1.93 \text{ MB/sec} \approx 15.4 \text{ Mbps}$$
  *At peak (15,500 reads/sec)*: $\approx 7.75 \text{ MB/sec} \approx \mathbf{62 \text{ Mbps}}$.
  *Easily handled by a single Gigabit network interface; negligible egress cost.*

---

## 3. High-Level Architecture

```
                                  [ User / Client ]
                                         │
                                         ▼
                            [ Global Anycast DNS / CDN ]
                             (Cloudflare Edge Caching)
                                         │
                                         ▼
                            [ Cloud Load Balancer ]
                               (AWS ALB / Envoy)
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
          [ FastAPI Worker 1 ]                        [ FastAPI Worker N ]
         (Stateless App Tier)                        (Stateless App Tier)
                   │                                           │
          ┌────────┴─────────────────┬─────────────────────────┴────────┐
          ▼                          ▼                                  ▼
   [ Redis Cluster ]        [ PostgreSQL Primary ]             [ Click Event Stream ]
   - Cache-Aside Layer      (ACID Writes, Unique Constraints)   (Async Background Tasks)
   - Sliding Window Limits           │                                  │
   - Idempotency Store               ▼                                  ▼
                            [ Read Replica 1..M ]              [ Analytics Aggregator ]
                            (Analytic queries & Reads)          (ClickHouse / BigQuery)
```

---

## 4. Deep-Dive Data Flows

### 4.1 URL Redirection Flow (Read Path - $P_{99} < 10\text{ms}$)

```
Client              FastAPI             Redis Cache          PostgreSQL
  │                     │                    │                   │
  │── 1. GET /{code} ──>│                    │                   │
  │                     │── 2. GET url:{c} ─>│                   │
  │                     │<─ 3. Cache HIT ────│                   │
  │<─ 4. HTTP 307 ──────│                    │                   │
  │                     │                                        │
  │ (If Cache MISS)     │── 5. Cache MISS ──>│                   │
  │                     │── 6. SELECT WHERE code = c ───────────>│
  │                     │<─ 7. Return URLModel ──────────────────│
  │                     │── 8. SET url:{c} (TTL=24h) ───────────>│
  │<─ 9. HTTP 307 ──────│                                        │
  │                     │                                        │
  │ (Background Task)   │── 10. Atomic click_count = click_count + 1
  │                     │── 11. Async log ClickEvent (ip_hash, ua, ref)
```

---

### 4.2 URL Creation Flow (Write Path - Conflict Free)

1. Client sends `POST /api/v1/urls` with `{"url": "https://..."}` and optional `Idempotency-Key`.
2. **Rate Limiting Check**: Redis sliding window verifies client IP is under 100 requests/minute.
3. **Idempotency Verification**: If key is cached, instantly return previous response (`Idempotency-Replay: true`).
4. **Code Generation**:
   - If `custom_alias` provided: Attempt insert; if duplicate, catch database unique constraint and return `409 Conflict`.
   - If auto-generated: Generate 7-character Base62 string.
5. **Database Transaction**: Insert `URLModel` with row commit.
6. **Cache Invalidation/Priming**: Write `url:<short_code>` to Redis with 24-hour TTL.
7. Return `HTTP 201 Created` with `Location` header and complete metadata payload.

---

## 5. High Availability, Fault Tolerance & Disaster Recovery

### 5.1 Subsystem Degradation Matrix
| Subsystem Failure | Impact on System | Automated Mitigation Strategy |
|---|---|---|
| **Redis Outage** | Cache misses surge to 100% | System seamlessly falls back to PostgreSQL queries. In-memory sliding window absorbs rate limiting. URL creation persists to DB without failure. |
| **PostgreSQL Primary Crash** | Write operations pause momentarily | Multi-AZ automated failover (Patroni / AWS Aurora) promotes standby replica in < 30 seconds. Read redirects continue serving from Redis with zero downtime. |
| **Network Partition (Split-Brain)** | Cross-region connectivity drop | Redis Sentinel / Cluster quorum rules ensure majority partition accepts writes; isolated partition refuses writes to prevent split-brain anomalies. |

### 5.2 CAP Theorem Trade-Off
* **Read Path (Redirects)**: Prioritizes **Availability and Partition Tolerance (AP)**. A slightly stale redirect or transient analytic delay is preferable to returning an HTTP 500 error to end users.
* **Write Path (Creation)**: Prioritizes **Consistency and Partition Tolerance (CP)**. Strict ACID guarantees are enforced via PostgreSQL unique indexes to prevent multiple users from owning the same short code.

---

## 6. Database Sharding & Future Scaling

When write traffic exceeds 10,000 writes/sec or storage exceeds single-node SSD capacity:
1. **Range-Based Sharding vs. Hash-Based Sharding**:
   - Hash-based sharding on `MD5(short_code) % NumberOfShards` distributes read and write load uniformly across DB nodes, eliminating hot partitions.
2. **Consistent Hashing**:
   - Consistent hashing rings minimize key remapping when scaling database shards or Redis cache nodes.
3. **Multi-Region Anycast Edge Deployment**:
   - Deploy stateless FastAPI read-only containers in US-East, US-West, EU-Central, and AP-East.
   - Redis read replicas placed locally in each cloud region deliver localized $< 2\text{ms}$ redirect execution globally.
