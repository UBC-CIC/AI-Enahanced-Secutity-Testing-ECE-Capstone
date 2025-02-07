# Load Test

## Objectives
 1. Verify EKS Auto-Scaling
Ensure that the HPA in EKS scales as expected when CPU or memory usage crosses defined thresholds.
 2. Measure Response Times
Collect key performance metrics (latency, error rates) under various load levels.
 3. Determine Concurrent User Capacity
Identify the maximum concurrency the application can handle while still meeting SLOs.
 4. Monitor Resource Utilization
Confirm that pod-level metrics (CPU/Memory) and cluster-level metrics align with scaling events.

## Scenarios

1. Light Load
- Concurrency: 10 concurrent users
- Duration: 5 minutes
- Endpoints: Currently 70% GET /, 30% POST /zap/basescan (see code below)
- Expected Outcome:
  - No scaling event
  - CPU/memory well below HPA thresholds

2. Medium Load
- Concurrency: Ramp to 50 users, hold ~5 minutes, then ramp down (total ~10 minutes)
- Endpoints: 70% GET /, 30% POST /zap/basescan
- Expected Outcome:
  - Possible horizontal pod scaling
  - Response times remain acceptable

3. Heavy Load
- Concurrency: Ramp to 100 users, hold 10 minutes, then ramp down (~15 minutes total)
- Endpoints: 70% GET /, 30% POST /zap/basescan
- Expected Outcome:
  - Scaling event as CPU/memory usage crosses threshold
  - Response times, error rates still within SLOs


## Implementation

### Prerequisites
- locust
- prometheus-client
```
pip install locust prometheus-client 
```

### Locust Script
Path: `scripts/locust-load-test.py`

```python
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
```
### Locust Test

#### 1. Light Load Test
```
locust -f load_test.py --headless -u 10 -r 2 -t 5m 
```
- Users: 10
- Spawn rate: 2 users/second
- Duration: 5 minutes
- Expected: No scaling event

#### 2. Medium Load Test
```
locust -f load_test.py --headless -u 50 -r 5 -t 10m 
```
- Users: 50
- Spawn rate: 5 users/second
- Duration: 10 minutes
- Expected: Possible pod scaling

#### 3. Heavy Load Test
```
locust -f load_test.py --headless -u 100 -r 10 -t 15m 
```
- Users: 100
- Spawn rate: 10 users/second
- Duration: 15 minutes
- Expected: Definite scaling event

## Monitoring Setup

1. Install Prometheus and Grafana:
```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack
```

2. Grafana Port Forward
```
kubectl port-forward svc/prometheus-grafana 3000:80
```
Open http://localhost:3000 to visualize CPU, memory, and custom Locust metrics if you scrape :8000 from your load generator.

3. (Optional) Create your own Grafana Dashboard

4. Locust web UI
```locust -f load_test.py```
Then open http://localhost:8089

## Success Criteria

1. Performance Metrics:
- Health check response time: < 200ms
- ZAP scan response time: < 30s
- Error rate: < 1%

2. Scaling Metrics:
- Scale up when CPU > 70%
- Scale up within 2 minutes
- Maximum pods: 10
- Minimum pods: 2

3. Resource Usage:
- CPU: < 80% sustained
- Memory: < 80% sustained

## Analyzing Results
1. Key metrics to analyze:
- Request rate vs Error rate
- Response time distribution
- Pod scaling events (e.g., `kubectl get hpa -w`)
- Resource utilization patterns

2. Document findings:
- Maximum sustainable load before SLO violations
- Whether scaling thresholds/policies are sufficient
- Any performance bottlenecks or resource constraints
