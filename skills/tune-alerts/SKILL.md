---
name: tune-alerts
description: >
  Tune alerting rules using data-driven thresholds from baselines. Use when the
  user says "my alerts are noisy", "tune this alert", "reduce alert fatigue",
  "what threshold should I use", "alert is firing too often", "create an alerting rule",
  "write a PrometheusRule", "suggest alert thresholds", "review my alerts",
  or needs help with Prometheus alerting configuration.
version: 1.0.0
---

# Data-Driven Alert Tuning

Tune alerting thresholds using actual baseline data from `.sre/baselines/`, not guesswork. Noisy alerts erode trust — data-driven thresholds are the fix.

**Prerequisite:** `.sre/` context. Baselines are critical for this skill.

## Phase 1: Understand the Alert

If the user provides an existing alert rule, parse it for:
- The metric being monitored
- Current threshold
- `for:` duration (pending time)
- Labels and routing

If creating a new alert, determine what to alert on based on the service's available metrics.

## Phase 2: Query Historical Distribution

For the metric in question, query its distribution over 7-30 days:
```bash
# Percentiles over time
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=quantile_over_time(0.50, <metric>[7d])'
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=quantile_over_time(0.95, <metric>[7d])'
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=quantile_over_time(0.99, <metric>[7d])'

# Standard deviation (for anomaly-based thresholds)
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=stddev_over_time(<metric>[7d])'
```

## Phase 3: Recommend Thresholds

### Strategy: Baseline + Headroom
- **Warning**: p95 of historical values (catches real anomalies, ignores normal variance)
- **Critical**: p99 + 1 standard deviation (fires only for true outliers)
- **`for:` duration**: At least 5m for infrastructure, 2m for user-facing latency

### Anti-Flapping
If the alert has been firing/resolving frequently:
```bash
# Check how often the metric crosses the current threshold
curl -s --get "${PROMETHEUS_URL}/api/v1/query_range" \
  --data-urlencode 'query=<metric> > <current_threshold>' \
  --data-urlencode 'start=<7d_ago>' \
  --data-urlencode 'end=<now>' \
  --data-urlencode 'step=5m'
```
Count the number of transitions. If > 10/day, the threshold is too tight.

## Phase 4: Generate Tuned Alert Rule

Output a PrometheusRule YAML:
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: <service>-alerts
  namespace: monitoring
  labels:
    release: monitoring  # matches kube-prometheus-stack selector
spec:
  groups:
  - name: <service>.rules
    rules:
    - alert: <ServiceName>HighCPU
      expr: |
        sum(rate(container_cpu_usage_seconds_total{
          namespace="<ns>",pod=~"<pattern>",container!=""
        }[5m])) > <data-driven-threshold>
      for: 5m
      labels:
        severity: warning
        service: <name>
      annotations:
        summary: "{{ $labels.pod }} CPU usage above baseline"
        description: "CPU is {{ $value | humanize }} cores (baseline: <baseline> cores, threshold: <threshold> cores)"
        runbook_url: ""
```

## Phase 5: Compare Old vs New

If tuning an existing alert, show the comparison:
```
Current threshold: 0.5 cores (fires 12x/day)
Recommended threshold: 0.85 cores (p95 + headroom)
Expected fire rate: ~1x/week (based on 7d history)
```

Offer to apply via `kubectl apply` if in a Kubernetes environment.
