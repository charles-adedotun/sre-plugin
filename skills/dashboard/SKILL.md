---
name: dashboard
description: >
  Generate a Grafana dashboard for a service using discovered infrastructure context.
  Use when the user asks to "create a dashboard", "generate a dashboard for X",
  "build a monitoring dashboard", "make a Grafana dashboard", "I need to monitor X",
  "create panels for X", "generate dashboard JSON", "build a RED dashboard",
  "build a USE dashboard", "set up observability for X", "push a dashboard to Grafana",
  "visualize metrics for X", or needs a production-ready Grafana dashboard.
version: 1.0.0
---

# Context-Aware Grafana Dashboard Generator

Generate production-ready Grafana dashboard JSON using the `.sre/` context directory. Unlike template-based approaches, this skill uses **your actual metrics and baselines** — no hallucinated metric names, no hardcoded thresholds.

**Prerequisite:** Run the `discover` skill first to populate `.sre/`. If `.sre/` doesn't exist, tell the user to run `/discover` first.

## Phase 1: Load Service Context

Read the service context from `.sre/`:
1. Read `.sre/config.yaml` for Prometheus/Grafana connection details
2. Read `.sre/services/<service>.yaml` for available metrics and labels
3. Read `.sre/baselines/<service>.yaml` for threshold values
4. Read `.sre/topology.yaml` for upstream/downstream dependencies

If the user names a service, match it against the files in `.sre/services/`. If ambiguous, list available services and ask.

## Phase 2: Choose Dashboard Strategy

Based on what metrics are available for the service:

### Scenario A: Full Application Metrics Available
If `metrics.application` in the service context contains HTTP or gRPC metrics:
- Use **RED method** (Rate, Errors, Duration)
- Build 4 rows: Traffic, Errors, Latency, Infrastructure

### Scenario B: Container Metrics Only (Most Common)
If only `metrics.container` and `metrics.kube_state` are available:
- Use **USE method** (Utilization, Saturation, Errors)
- Build 4 rows: Overview, CPU/Memory, Network, Pod Health
- This is the most common scenario — most services don't expose /metrics

### Scenario C: Hybrid
Some services have both. Build a 6-row dashboard combining RED + USE.

## Phase 3: Build Dashboard JSON

### Dashboard Shell
Every dashboard starts with this structure:
```json
{
  "dashboard": {
    "title": "<Service Name> — SRE Dashboard",
    "tags": ["sre-skills", "auto-generated", "<namespace>"],
    "timezone": "browser",
    "refresh": "30s",
    "time": { "from": "now-1h", "to": "now" },
    "templating": { "list": [] },
    "panels": [],
    "annotations": { "list": [] },
    "schemaVersion": 39
  },
  "overwrite": true,
  "folderId": 0
}
```

### Template Variables (Always Include)
Add template variables for filtering. Use the actual labels from `.sre/services/<name>.yaml`:

```json
{
  "name": "namespace",
  "type": "query",
  "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
  "query": "label_values(kube_pod_info, namespace)",
  "current": { "text": "<namespace from context>", "value": "<namespace>" },
  "refresh": 2
}
```

Add a `pod` variable filtered by namespace:
```json
{
  "name": "pod",
  "type": "query",
  "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
  "query": "label_values(kube_pod_info{namespace=\"$namespace\"}, pod)",
  "includeAll": true,
  "refresh": 2
}
```

**Find the datasource UID:** If Grafana is accessible, query:
```bash
curl -s -u admin:<password> "${GRAFANA_URL}/api/datasources" | python3 -c "
import json,sys
for ds in json.load(sys.stdin):
    if ds['type'] == 'prometheus':
        print(f'Prometheus UID: {ds[\"uid\"]}')"
```
If not accessible, use `"${DS_PROMETHEUS}"` as a placeholder — the user can set it on import.

### Panel Grid System
Grafana uses a 24-unit wide grid. Standard layout:
- Full-width panel: `w=24`
- Half-width: `w=12`
- Third-width: `w=8`
- Quarter-width: `w=6`
- Row height: typically `h=8` for timeseries, `h=4` for stat panels

### Row 1: Overview (stat panels)
4 stat panels showing key numbers at a glance:

| Panel | Query | Thresholds |
|-------|-------|-----------|
| Pod Count | `count(kube_pod_status_phase{namespace="$namespace",pod=~"<pattern>",phase="Running"})` | green ≥ replicas, red < replicas |
| CPU Usage | `sum(rate(container_cpu_usage_seconds_total{namespace="$namespace",pod=~"<pattern>",container!=""}[5m]))` | green < baseline×1.5, yellow < baseline×2, red ≥ baseline×2 |
| Memory Usage | `sum(container_memory_working_set_bytes{namespace="$namespace",pod=~"<pattern>",container!=""})` | same threshold pattern from baselines |
| Restarts (1h) | `sum(increase(kube_pod_container_status_restarts_total{namespace="$namespace",pod=~"<pattern>"}[1h]))` | green = 0, yellow = 1-2, red ≥ 3 |

Use stat panel type (`"type": "stat"`) with `gridPos: {x: 0/6/12/18, y: 0, w: 6, h: 4}`.

**Threshold derivation from baselines:**
- Read `.sre/baselines/<service>.yaml`
- CPU warning = `avg_cores × 1.5`, critical = `avg_cores × 2`
- Memory warning = `avg_bytes × 1.3`, critical = `avg_bytes × 1.5`
- If baselines aren't available, omit thresholds (don't guess)

### Row 2: CPU & Memory (timeseries)
Two half-width timeseries panels:

**CPU Usage by Pod:**
```
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="$namespace",pod=~"<pattern>",container!=""}[5m]))
```

**Memory Usage by Pod:**
```
sum by (pod) (container_memory_working_set_bytes{namespace="$namespace",pod=~"<pattern>",container!=""})
```

Use `gridPos: {x: 0, y: 4, w: 12, h: 8}` and `{x: 12, y: 4, w: 12, h: 8}`.

### Row 3: Network (timeseries)
Two half-width panels:

**Network Receive:**
```
sum by (pod) (rate(container_network_receive_bytes_total{namespace="$namespace",pod=~"<pattern>"}[5m]))
```

**Network Transmit:**
```
sum by (pod) (rate(container_network_transmit_bytes_total{namespace="$namespace",pod=~"<pattern>"}[5m]))
```

### Row 4: Pod Health (table + timeseries)
**Pod Status Table** (half-width):
```
kube_pod_status_phase{namespace="$namespace",pod=~"<pattern>"} == 1
```
Format as table showing pod name + phase.

**Restart Rate** (half-width timeseries):
```
rate(kube_pod_container_status_restarts_total{namespace="$namespace",pod=~"<pattern>"}[5m])
```

### Row 5: Upstream/Downstream Health (if topology available)
Read `.sre/topology.yaml` for the service's dependencies.
For each dependency, add a stat panel showing its pod count and restart count. This gives the operator a single-pane view of the service AND its dependencies.

Use a collapsible row: `{"type": "row", "title": "Dependencies", "collapsed": true, "panels": [...]}`.

### Row 6: Logs (if Loki available)
If `.sre/services/<name>.yaml` has `loki.available: true`:

**Log Panel:**
```
{namespace="$namespace", container="<container from context>"} |= ""
```
Use `"type": "logs"` panel. If `log_format: structured_json`, add JSON parsing: `| json`.

**Log Rate by Level** (timeseries, if structured logs):
```
sum by (level) (rate({namespace="$namespace", container="<container>"}
  | json
  | __error__="" [5m]))
```

## Phase 4: Assemble and Output

Combine all rows into the panels array with correct `gridPos` values. Each row's `y` position must account for the height of all rows above it.

**Output the complete JSON** in a code block. The user can copy-paste this into Grafana (Dashboards → Import → Paste JSON).

## Phase 5: Push to Grafana (Optional)

If Grafana URL and credentials are available:
```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -u "admin:<password>" \
  "${GRAFANA_URL}/api/dashboards/db" \
  -d '<dashboard JSON>'
```

Parse the response for the dashboard URL:
```json
{"id":1,"slug":"frontend-sre-dashboard","status":"success","uid":"abc123","url":"/d/abc123/frontend-sre-dashboard","version":1}
```

Report: `Dashboard created: ${GRAFANA_URL}/d/<uid>/<slug>`

Register the dashboard in `.sre/dashboards.yaml`:
```yaml
dashboards:
  - service: frontend
    uid: abc123
    url: /d/abc123/frontend-sre-dashboard
    created_at: <ISO timestamp>
    type: use  # or red, hybrid
```

## Key Principles

1. **Never hallucinate metrics.** Only use metric names that were discovered and recorded in `.sre/services/<name>.yaml`. If a metric isn't listed, don't use it.
2. **Derive thresholds from baselines.** If `.sre/baselines/<name>.yaml` exists, use it. If not, omit thresholds rather than guessing.
3. **Include dependencies.** A service dashboard without upstream/downstream context misses the point. Use the topology.
4. **Logs complete the picture.** If Loki is available, always add a logs panel. Metrics tell you WHAT is wrong; logs tell you WHY.
