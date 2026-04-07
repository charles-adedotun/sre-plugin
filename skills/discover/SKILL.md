---
name: discover
description: >
  Discover and index infrastructure for SRE context. Use when the user asks to
  "discover my services", "scan prometheus", "build service map", "what metrics
  do I have", "index my infrastructure", "set up SRE context", "learn my cluster",
  "what's running in my cluster", "map my services", or needs to populate the
  .sre/ context directory before running other SRE skills.
version: 1.0.0
---

# Infrastructure Discovery

Crawl Prometheus, Loki, and Kubernetes to build a structured context of the user's infrastructure. This context is stored in `.sre/` and consumed by all other SRE skills.

**This skill is the foundation.** Run it before using dashboard, investigate, define-slo, or tune-alerts.

## Prerequisites

Need connection details for at least Prometheus. Loki and Grafana are optional but improve coverage.

Check environment variables first:
```bash
echo "PROMETHEUS_URL=${PROMETHEUS_URL:-not set}"
echo "LOKI_URL=${LOKI_URL:-not set}"
echo "GRAFANA_URL=${GRAFANA_URL:-not set}"
echo "KUBECONFIG=${KUBECONFIG:-not set}"
```

If not set, ask the user for Prometheus URL. Common defaults:
- In-cluster: `http://localhost:9090` (port-forwarded) or `http://prometheus-server.monitoring:9090`
- kind/minikube: `http://localhost:30090` (NodePort)

## Phase 1: Initialize Context Directory

Create the `.sre/` directory structure in the current working directory:

```
.sre/
├── config.yaml          # connection URLs, discovery timestamp
├── topology.yaml        # service dependency graph
├── services/            # one YAML per service
│   ├── frontend.yaml
│   ├── cartservice.yaml
│   └── ...
├── baselines/           # golden signal baselines per service
│   ├── frontend.yaml
│   └── ...
├── incidents/           # incident memory (written by investigate skill)
└── dashboards.yaml      # registry of created dashboards
```

Write `.sre/config.yaml` with the connection details:
```yaml
prometheus_url: <url>
loki_url: <url or null>
grafana_url: <url or null>
discovered_at: <ISO timestamp>
kubernetes_context: <context name or null>
# NEVER write passwords or tokens here — use GRAFANA_PASSWORD / GRAFANA_TOKEN env vars
```

**Security rule:** Do not write credentials to `.sre/config.yaml`. The file may be read by other tools. Always source Grafana credentials from `$GRAFANA_PASSWORD` or `$GRAFANA_TOKEN` at runtime.

## Phase 2: Enumerate Services

Query Prometheus to find all services/jobs being monitored.

### Method A: Kubernetes namespace (preferred if kubectl available)
```bash
# Get all deployments across namespaces
kubectl get deployments --all-namespaces -o json
```
Parse the output to get: namespace, deployment name, labels, replicas.

### Method B: Prometheus label discovery
```bash
# Get all unique job labels — these represent monitored services
curl -s "${PROMETHEUS_URL}/api/v1/label/job/values"
```

### Method C: Combine both
Use Kubernetes for service topology and Prometheus for metric availability. Cross-reference deployment names with Prometheus job labels.

**Filter out system services** (kube-system, monitoring namespace internals) unless the user specifically requests them. Focus on application workloads.

## Phase 3: Metric Discovery Per Service

For each discovered service, find what metrics are available.

### Container/Resource Metrics (from cAdvisor/kubelet)
These are almost always available for any pod running in Kubernetes:
```bash
# CPU usage for a specific pod/deployment
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=container_cpu_usage_seconds_total{namespace="<ns>",pod=~"<deployment>.*",container!=""}'

# Memory usage
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=container_memory_working_set_bytes{namespace="<ns>",pod=~"<deployment>.*",container!=""}'

# Network I/O
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=container_network_receive_bytes_total{namespace="<ns>",pod=~"<deployment>.*"}'
```

### Application-Level Metrics (from service /metrics or OTel)
Check if the service exposes application metrics:
```bash
# Search for any metric with the service name in the job label
curl -s --get "${PROMETHEUS_URL}/api/v1/label/__name__/values" \
  --data-urlencode 'match[]={job="<job_label>"}'
```

Look for standard patterns:
- **HTTP metrics**: `http_requests_total`, `http_request_duration_seconds_*`, `http_server_*`
- **gRPC metrics**: `grpc_server_handled_total`, `grpc_server_handling_seconds_*`, `rpc_server_*`
- **Custom metrics**: anything not starting with `container_`, `kube_`, `node_`, `process_`, `go_`

### kube-state-metrics
Always available in kube-prometheus-stack:
```bash
# Pod status, restarts, readiness
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=kube_pod_container_status_restarts_total{namespace="<ns>",pod=~"<deployment>.*"}'
```

## Phase 4: Capture Baselines

For each service, query recent metric values to establish "normal" behavior:

```bash
# Average CPU over last 1 hour (or longer if available)
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=avg(rate(container_cpu_usage_seconds_total{namespace="<ns>",pod=~"<deployment>.*",container!=""}[5m]))'

# Average memory
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=avg(container_memory_working_set_bytes{namespace="<ns>",pod=~"<deployment>.*",container!=""})'

# If HTTP metrics exist: request rate, error rate, latency percentiles
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_requests_total{job="<job>"}[5m]))'

curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{job="<job>"}[5m])))'
```

**Important:** If the cluster is new or metrics have less than 1 hour of data, note this in the baseline and use shorter windows. Baselines improve over time — re-run discover periodically.

## Phase 5: Discover Topology

Try to determine service-to-service dependencies:

### Method A: Kubernetes service references
Parse deployment env vars for service addresses:
```bash
kubectl get deployment <name> -n <ns> -o jsonpath='{.spec.template.spec.containers[0].env}'
```
Look for env vars containing other service hostnames (e.g., `CART_SERVICE_ADDR=cartservice:7070`).

### Method B: Prometheus metrics (if available)
Look for client-side metrics that reference target services:
```bash
# gRPC client metrics with target service labels
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=grpc_client_started_total'

# HTTP client metrics
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=http_client_requests_total'
```

## Phase 6: Loki Log Discovery

If Loki URL is available, discover log labels:
```bash
# Available labels
curl -s "${LOKI_URL}/loki/api/v1/labels"

# Values for namespace label
curl -s "${LOKI_URL}/loki/api/v1/label/namespace/values"

# Values for app/container labels
curl -s "${LOKI_URL}/loki/api/v1/label/app/values"
curl -s "${LOKI_URL}/loki/api/v1/label/container/values"

# Sample a few log lines to detect format (JSON structured vs plaintext)
curl -s --get "${LOKI_URL}/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="<ns>",container="<container>"}' \
  --data-urlencode 'limit=5' \
  --data-urlencode 'start=<epoch_ns_5min_ago>' \
  --data-urlencode 'end=<epoch_ns_now>'
```

Detect log format by checking if the log line starts with `{` (JSON structured) or not.

## Phase 7: Check Existing Dashboards

If Grafana URL is available:
```bash
# List existing dashboards
curl -s -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
  "${GRAFANA_URL}/api/search?type=dash-db" | python3 -c "
import json,sys
for d in json.load(sys.stdin):
    print(f'{d[\"uid\"]:20s} {d[\"title\"]}')"
```

Or if using Grafana with default creds:
```bash
curl -s -u admin:<password> "${GRAFANA_URL}/api/search?type=dash-db"
```

## Phase 8: Write Context Files

### Service file template (`.sre/services/<name>.yaml`)
```yaml
name: <service-name>
namespace: <kubernetes-namespace>
deployment: <deployment-name>
pod_pattern: "<deployment>.*"
replicas: <count>
discovered_at: <ISO timestamp>

metrics:
  container:
    - container_cpu_usage_seconds_total
    - container_memory_working_set_bytes
    - container_network_receive_bytes_total
    - container_network_transmit_bytes_total
  kube_state:
    - kube_pod_container_status_restarts_total
    - kube_pod_status_phase
  application: []  # populated if app metrics found
    # - http_requests_total
    # - http_request_duration_seconds_bucket

labels:
  job: <prometheus job label if found>
  namespace: <ns>
  container: <container name>
  pod_regex: "<deployment>.*"

loki:
  available: true/false
  app_label: <value for {app="X"} or {container="X"}>
  log_format: structured_json | plaintext | unknown
  sample_fields: [severity, time, message]  # if JSON
```

### Baselines file template (`.sre/baselines/<name>.yaml`)
```yaml
name: <service-name>
captured_at: <ISO timestamp>
window: "1h"  # or "7d" etc

cpu:
  avg_cores: <float>
  max_cores: <float>
memory:
  avg_bytes: <int>
  max_bytes: <int>
network:
  receive_bytes_per_sec: <float>
  transmit_bytes_per_sec: <float>
restarts:
  total: <int>
  rate_per_hour: <float>

# Only if application metrics exist:
http:
  rps: <float>
  error_rate_pct: <float>
  p50_ms: <float>
  p95_ms: <float>
  p99_ms: <float>
```

### Topology file template (`.sre/topology.yaml`)
```yaml
discovered_at: <ISO timestamp>
method: env_vars | metrics | manual

services:
  frontend:
    upstream: []
    downstream: [cartservice, productcatalogservice, currencyservice, checkoutservice, recommendationservice, adservice]
  checkoutservice:
    upstream: [frontend]
    downstream: [paymentservice, shippingservice, emailservice, cartservice, currencyservice, productcatalogservice]
  # ... etc
```

## Output

After discovery completes, print a summary:
```
Discovery complete:
  Services found: 11
  With app metrics: 0 (container metrics available for all)
  Loki logs: 11 streams
  Topology: 24 edges discovered
  Context written to: .sre/
```

Recommend running `/dashboard <service>` next to generate a Grafana dashboard.
