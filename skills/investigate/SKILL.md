---
name: investigate
description: >
  Investigate incidents and anomalies using live Prometheus and Loki data with
  infrastructure context. Use when the user reports "service is down",
  "high error rate", "latency spike", "pods crashing", "something is wrong",
  "investigate this alert", "help me debug", "why is X slow", "check service health",
  "what's happening with X", "run an incident investigation", or any operational
  problem requiring data-driven diagnosis.
version: 1.0.0
---

# Incident Investigation

Investigate operational issues by correlating live metrics, logs, and infrastructure context. Unlike template-based runbooks, this skill uses `.sre/` context to know your services, their baselines, and their dependencies — enabling reasoning, not just checklist execution.

**Prerequisite:** `.sre/` context from the `discover` skill. Can work without it but is significantly more effective with context.

## Phase 1: Understand the Symptom

Parse the user's report to identify:
1. **Affected service** — match against `.sre/services/` files
2. **Symptom type** — one of: errors, latency, availability, resource exhaustion, unknown
3. **When it started** — if known, use as time range; otherwise default to last 30 minutes

## Phase 2: Triage — Compare Against Baselines

Read `.sre/baselines/<service>.yaml` and query current values:

### Check Golden Signals
```bash
# Current CPU vs baseline
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(rate(container_cpu_usage_seconds_total{namespace="<ns>",pod=~"<pattern>",container!=""}[5m]))'

# Current memory vs baseline
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(container_memory_working_set_bytes{namespace="<ns>",pod=~"<pattern>",container!=""})'

# Recent restarts
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>",pod=~"<pattern>"}[30m]))'

# Pod count vs expected replicas
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=kube_deployment_status_replicas_available{namespace="<ns>",deployment="<name>"}'
```

Compare each value against the baseline. Flag anything that's:
- CPU > 2× baseline
- Memory > 1.5× baseline
- Restarts > 0 in last 30m
- Available replicas < desired replicas

## Phase 3: Trace the Blast Radius

Read `.sre/topology.yaml` and check upstream + downstream services:

For each dependency:
```bash
# Quick health check: pod count and restart count
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=kube_deployment_status_replicas_available{namespace="<ns>",deployment="<dep>"}'
curl -s --get "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>",pod=~"<dep>.*"}[30m]))'
```

If a downstream dependency is unhealthy, it's likely the root cause (not the reported service).

## Phase 4: Pull Logs

Query Loki for recent error logs from the affected service:
```bash
curl -s --get "${LOKI_URL}/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="<ns>",container="<container>"} |= "error" or |= "Error" or |= "ERROR" or |= "fatal" or |= "panic"' \
  --data-urlencode 'limit=50' \
  --data-urlencode 'start=<30min_ago_epoch_ns>' \
  --data-urlencode 'end=<now_epoch_ns>'
```

If structured JSON logs (`log_format: structured_json` in service context):
```bash
curl -s --get "${LOKI_URL}/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="<ns>",container="<container>"} | json | severity=~"error|fatal|panic"' \
  --data-urlencode 'limit=50'
```

## Phase 5: Check Incident History

Read `.sre/incidents/` for past incidents involving the same service. Similar symptoms may indicate a recurring issue.

## Phase 6: Generate Investigation Report

Structure the output as:

```
## Investigation Report: <service> — <symptom>
**Time:** <timestamp>
**Severity:** <estimated based on blast radius and deviation from baseline>

### Current State vs Baseline
| Signal | Current | Baseline | Status |
|--------|---------|----------|--------|
| CPU    | 0.8 cores | 0.3 cores | ⚠ 2.7× baseline |
| Memory | 512 MB | 450 MB | ✓ normal |
| Restarts | 3 | 0/hr | ✗ abnormal |
| Pods | 1/1 | 1 | ✓ |

### Blast Radius
- upstream: <service1> ✓, <service2> ✓
- downstream: <service3> ✗ (2 restarts in 30m), <service4> ✓

### Hypothesis
Based on the data:
1. <Most likely cause based on evidence>
2. <Alternative explanation>

### Evidence (Logs)
<relevant error log excerpts>

### Recommended Actions
1. <specific action based on evidence>
2. <specific action>
```

## Phase 7: Record Incident (Optional)

If the user confirms this is a real incident, write to `.sre/incidents/<date>-<service>-<summary>.yaml`:
```yaml
service: <name>
started_at: <ISO timestamp>
symptoms: [<list>]
root_cause: <if determined>
resolution: <if resolved>
signals:
  cpu_deviation: 2.7x
  restarts: 3
similar_to: []  # references to past incidents
```

This builds institutional memory — future investigations can reference past patterns.
