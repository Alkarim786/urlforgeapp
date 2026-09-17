# URLForge Performance Benchmarks & Load Testing

This directory provides automated load testing and benchmarking tools to measure:
- P50, P90, P95, and P99 latency percentiles
- Requests per second (RPS) throughput
- Cache-Aside latency advantages (Redis vs. PostgreSQL)

---

## 1. Automated Benchmark Harness

Run the automated async benchmark suite:

```bash
python benchmarks/benchmark_runner.py
```

This runs concurrent redirect requests across simulated workloads, measures percentile distributions, and writes the results to `benchmarks/results.md`.

---

## 2. Locust Load Testing

To simulate realistic distributed user traffic across web workers:

1. Install Locust:
   ```bash
   pip install locust
   ```

2. Launch the Locust headless load test:
   ```bash
   locust -f benchmarks/locustfile.py --headless -u 100 -r 10 --run-time 1m --host http://localhost:8000
   ```

3. Or launch with the interactive web UI:
   ```bash
   locust -f benchmarks/locustfile.py --host http://localhost:8000
   ```
   Open `http://localhost:8089` in your browser.

---

## 3. Traffic Ratio Distribution

The load tests adhere to the production traffic profile:
- **90% Read Weight**: `GET /{short_code}` redirects (cache-aside path).
- **8% Write Weight**: `POST /api/v1/urls` creation with collision retry simulation.
- **2% Analytics Weight**: `GET /api/v1/urls/{short_code}/analytics` aggregated queries.
