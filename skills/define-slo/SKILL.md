---
name: define-slo
description: >
  Define SLOs and calculate error budgets for services. Use when the user asks to
  "define an SLO", "set a service level objective", "calculate error budget",
  "how much error budget do I have", "what's my availability", "create SLO recording rules",
  "generate SLO burn rate alerts", "track reliability", or needs SLO/SLI definitions.
version: 1.0.0
---

# SLO Definition & Error Budget Tracking

Define Service Level Objectives, calculate error budgets, and generate Prometheus recording rules and burn-rate alert rules.

**Prerequisite:** `.sre/` context from the `discover` skill.

## Phase 1: Choose SLI Type

Based on available metrics in `.sre/services/<name>.yaml`:

### If HTTP/gRPC metrics available:
- **Availability SLI**: ratio of successful requests to total requests
  - `1 - (rate(http_requests_total{status=~"5.."}[window]) / rate(http_requests_total[window]))`
- **Latency SLI**: ratio of requests faster than threshold
  - `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[window]))`

### If container metrics only:
- **Availability SLI**: pod uptime ratio
  - `avg_over_time(kube_deployment_status_replicas_available{deployment="X"}[window]) / kube_deployment_spec_replicas{deployment="X"}`

## Phase 2: Set Targets

Common SLO targets (suggest based on service criticality):
| Tier | Availability | Latency p99 | Error Budget (30d) |
|------|-------------|-------------|-------------------|
| Critical (payment, auth) | 99.95% | based on baseline p99 × 1.5 | 21.6 min |
| Standard (API, frontend) | 99.9% | based on baseline p99 × 2 | 43.2 min |
| Best-effort (batch, internal) | 99.5% | N/A | 3.6 hours |

Use baselines from `.sre/baselines/<name>.yaml` to inform latency targets.

## Phase 3: Calculate Error Budget

```
Error budget = 1 - SLO target
Budget minutes (30d) = 30 * 24 * 60 * (1 - SLO)
```

Query current consumption:
```bash
# If availability SLI:
# Total errors in window / total requests in window
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(increase(http_requests_total{job="<job>",status=~"5.."}[30d])) / sum(increase(http_requests_total{job="<job>"}[30d]))'
```

## Phase 4: Generate Artifacts

### Prometheus Recording Rules (YAML)
```yaml
groups:
- name: slo:<service>
  rules:
  - record: slo:<service>:availability:ratio_rate5m
    expr: 1 - (sum(rate(http_requests_total{job="<job>",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="<job>"}[5m])))
  - record: slo:<service>:error_budget:remaining
    expr: 1 - (slo:<service>:errors:ratio_30d / (1 - <SLO_TARGET>))
```

### Multi-window Burn Rate Alerts
```yaml
groups:
- name: slo:<service>:alerts
  rules:
  - alert: SLOBurnRateCritical
    expr: slo:<service>:availability:ratio_rate5m < <SLO> AND slo:<service>:availability:ratio_rate1h < <SLO>
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "<service> is burning error budget at critical rate"
```

## Phase 5: Update Context

Write SLO definition to `.sre/services/<name>.yaml` under the `slos` field:
```yaml
slos:
  - type: availability
    target: 0.999
    window: 30d
    sli_query: "<PromQL>"
    defined_at: <ISO timestamp>
```

Generate a Grafana panel for the error budget (use the dashboard skill patterns) and suggest adding it to the service's existing dashboard.
