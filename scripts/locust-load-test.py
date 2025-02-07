from locust import HttpUser, task, between
from typing import Any, Dict
import random
from prometheus_client import start_http_server, Counter, Gauge

# Start a simple Prometheus metrics server on port 8000
# so we can scrape these custom metrics if desired.
start_http_server(8000)

BASE_URL = "OUR EKS LB URL"

class MetricsExporter:
    def __init__(self):
        self.request_count = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status']
        )
        self.response_time = Gauge(
            'http_response_time_seconds',
            'Latest response time in seconds',
            ['endpoint']
        )

    def record_request(self, method, endpoint, status, response_time):
        self.request_count.labels(method=method, endpoint=endpoint, status=status).inc()
        # Note: Using a Gauge means we only store the latest response time. 
        # For distribution metrics, consider using a Histogram or Summary instead.
        self.response_time.labels(endpoint=endpoint).set(response_time)

class BackendLoadTest(HttpUser):
    host = BASE_URL

    # Locust will wait between 1 and 3 seconds between tasks.
    wait_time = between(1, 3)
    metrics = MetricsExporter()
    
    @task(7)  # 70% of requests
    def health_check(self):
        with self.client.get("/", catch_response=True) as response:
            self.metrics.record_request(
                method="GET",
                endpoint="/",
                status=response.status_code,
                response_time=response.elapsed.total_seconds()
            )
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")

    @task(3)  # 30% of requests
    def zap_scan(self):
        payload = {"target_url": "https://example.com"}
        headers = {"Content-Type": "application/json"}
        with self.client.post("/zap/basescan", json=payload, headers=headers, catch_response=True) as response:
            self.metrics.record_request(
                method="POST",
                endpoint="/zap/basescan",
                status=response.status_code,
                response_time=response.elapsed.total_seconds()
            )
            if response.status_code != 200:
                response.failure(f"ZAP scan failed: {response.status_code}")
