"""Locust load test suite for URLForge URL Shortener.

Simulates production traffic patterns:
- 90% Read Weight: High-throughput redirects (Cache hits and DB fallback)
- 8% Write Weight: Short URL creation with collision retry simulation
- 2% Analytics Weight: Aggregated click metrics queries
"""

import random
import string
import uuid
from locust import HttpUser, between, task


class URLForgeUser(HttpUser):
    """Simulates active web users shortening links and clicking redirects."""

    wait_time = between(0.01, 0.05)  # High-throughput load test
    created_short_codes: list[str] = [
        "docs",
        "github",
        "fastapi",
        "python",
        "redis",
        "postgres",
    ]

    def on_start(self):
        """Seed a link for the virtual user."""
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.client.post(
            "/api/v1/urls",
            json={
                "url": f"https://example.com/target/{random_suffix}",
                "custom_alias": f"u_{random_suffix}",
            },
        )
        self.created_short_codes.append(f"u_{random_suffix}")

    @task(90)
    def redirect_lookup(self):
        """Simulate high-frequency redirect lookup (Cache-Aside path)."""
        code = random.choice(self.created_short_codes)
        with self.client.get(
            f"/{code}",
            headers={"User-Agent": "LocustBenchmark/1.0", "Referer": "https://google.com"},
            allow_redirects=False,
            catch_response=True,
            name="/{short_code} (Redirect)",
        ) as response:
            if response.status_code in (301, 302, 307, 308, 404):
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(8)
    def create_short_url(self):
        """Simulate URL shortening POST endpoint with random long targets."""
        token = uuid.uuid4().hex[:8]
        long_url = f"https://example.com/blog/article-{token}?ref=benchmark"
        with self.client.post(
            "/api/v1/urls",
            json={"url": long_url},
            name="/api/v1/urls (Create)",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                data = response.json()
                code = data.get("short_code")
                if code and len(self.created_short_codes) < 2000:
                    self.created_short_codes.append(code)
                response.success()
            elif response.status_code == 429:
                response.success()  # Rate limit hit is expected under intense load
            else:
                response.failure(f"URL create failed with status {response.status_code}")

    @task(2)
    def get_analytics(self):
        """Simulate analytics dashboard fetching."""
        code = random.choice(self.created_short_codes)
        with self.client.get(
            f"/api/v1/urls/{code}/analytics",
            name="/api/v1/urls/{code}/analytics",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Analytics query failed: {response.status_code}")
