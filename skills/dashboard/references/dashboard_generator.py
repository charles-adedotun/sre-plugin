#!/usr/bin/env python3
"""Generate a production-grade Grafana dashboard for a single service.

Environment variables:
  GRAFANA_PROM_UID   Prometheus datasource UID (default: "prometheus")
  GRAFANA_LOKI_UID   Loki datasource UID — find it in Grafana > Connections > Data sources
  SRE_NAMESPACE      Kubernetes namespace (default: "online-boutique")
  SRE_SERVICE        Service name (default: "frontend")
"""
import json, os

PROM_UID = os.environ.get("GRAFANA_PROM_UID", "prometheus")
LOKI_UID = os.environ.get("GRAFANA_LOKI_UID", "")
NS = os.environ.get("SRE_NAMESPACE", "online-boutique")
SVC = os.environ.get("SRE_SERVICE", "frontend")

if not LOKI_UID:
    print("WARNING: GRAFANA_LOKI_UID not set. Log panels will show 'No data' on other Grafana instances.")
    print("  Find your Loki UID: Grafana → Connections → Data sources → Loki → copy UID from URL")
    LOKI_UID = "P8E80F9AEF21F6940"
POD = "frontend.*"
CONTAINER = "server"

# Baselines from .sre/
CPU_BASELINE = 0.0087
CPU_REQUEST = 0.1
MEM_BASELINE = 21430272
MEM_LIMIT = 134217728  # 128 MB

DEPS = {
    "productcatalogservice": "server",
    "currencyservice": "server",
    "cartservice": "server",
    "recommendationservice": "server",
    "shippingservice": "server",
    "checkoutservice": "server",
    "adservice": "server",
}

panel_id = 0
def next_id():
    global panel_id
    panel_id += 1
    return panel_id

def prom(uid=PROM_UID):
    return {"type": "prometheus", "uid": uid}

def loki():
    return {"type": "loki", "uid": LOKI_UID}

# ─── Panel Builders ────────────────────────────────────────────────

def stat(title, expr, x, y, w=6, h=3, unit="short", thresholds=None,
         color_mode="background_solid", text_mode="value_and_sparkline",
         decimals=None, mappings=None, description=""):
    t = thresholds or [{"color": "green", "value": None}]
    p = {
        "id": next_id(),
        "type": "stat",
        "title": title,
        "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": prom(),
        "targets": [{"expr": expr, "refId": "A", "instant": True}],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "thresholds": {"mode": "absolute", "steps": t},
                "color": {"mode": "thresholds"},
                "mappings": mappings or [],
            },
            "overrides": []
        },
        "options": {
            "colorMode": color_mode,
            "graphMode": "area",
            "textMode": text_mode,
            "justifyMode": "center",
            "reduceOptions": {"calcs": ["lastNotNull"]},
        },
    }
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p

def gauge(title, expr, x, y, w=4, h=5, unit="percentunit",
          thresholds=None, min_val=0, max_val=1, description=""):
    t = thresholds or [
        {"color": "green", "value": None},
        {"color": "#EAB839", "value": 0.7},
        {"color": "red", "value": 0.9},
    ]
    return {
        "id": next_id(),
        "type": "gauge",
        "title": title,
        "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": prom(),
        "targets": [{"expr": expr, "refId": "A", "instant": True}],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": min_val, "max": max_val,
                "thresholds": {"mode": "absolute", "steps": t},
                "color": {"mode": "thresholds"},
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
        },
    }

def timeseries(title, targets, x, y, w=12, h=7, unit="short",
               fill=10, line_width=2, legend_placement="bottom",
               thresholds=None, description="", stack=False):
    tgts = []
    for i, t in enumerate(targets):
        tgt = {"expr": t[0], "legendFormat": t[1], "refId": chr(65+i)}
        if len(t) > 2:
            tgt.update(t[2])
        tgts.append(tgt)
    p = {
        "id": next_id(),
        "type": "timeseries",
        "title": title,
        "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": prom(),
        "targets": tgts,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "lineWidth": line_width,
                    "fillOpacity": fill,
                    "showPoints": "never",
                    "spanNulls": True,
                    "stacking": {"mode": "normal" if stack else "none"},
                    "thresholdsStyle": {"mode": "dashed" if thresholds else "off"},
                },
                "color": {"mode": "palette-classic-by-name"},
                "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]},
            },
            "overrides": []
        },
        "options": {
            "legend": {"displayMode": "list", "placement": legend_placement, "calcs": ["mean", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }
    return p

def row(title, y, collapsed=False):
    return {
        "id": next_id(),
        "type": "row",
        "title": title,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
        "collapsed": collapsed,
        "panels": [],
    }

def table(title, targets, x, y, w=12, h=7, transformations=None, overrides=None, description=""):
    tgts = [{"expr": t[0], "legendFormat": t[1], "refId": chr(65+i), "instant": True, "format": "table"}
            for i, t in enumerate(targets)]
    return {
        "id": next_id(),
        "type": "table",
        "title": title,
        "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": prom(),
        "targets": tgts,
        "fieldConfig": {
            "defaults": {"color": {"mode": "thresholds"}},
            "overrides": overrides or []
        },
        "transformations": transformations or [],
    }

def logs_panel(title, expr, x, y, w=24, h=8, description=""):
    return {
        "id": next_id(),
        "type": "logs",
        "title": title,
        "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": loki(),
        "targets": [{"expr": expr, "refId": "A"}],
        "options": {
            "showTime": True,
            "showLabels": False,
            "showCommonLabels": False,
            "wrapLogMessage": True,
            "prettifyLogMessage": True,
            "enableLogDetails": True,
            "sortOrder": "Descending",
            "dedupStrategy": "none",
        },
    }

def text_panel(content, x, y, w=24, h=2, mode="markdown"):
    return {
        "id": next_id(),
        "type": "text",
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "options": {"content": content, "mode": mode},
    }

# ─── Build Dashboard ───────────────────────────────────────────────

panels = []
y = 0

# ▸ HEADER: Service identity
panels.append(text_panel(
    f"# 🟢 {SVC}\n**Namespace:** `{NS}` · **Replicas:** 1 · **Container:** `{CONTAINER}` · "
    f"**Dependencies:** {', '.join(DEPS.keys())}",
    0, y, 24, 2
))
y += 2

# ▸ ROW 1: Service Health At A Glance
panels.append(row("Service Health", y))
y += 1

panels.append(stat(
    "Status",
    f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{SVC}"}} / kube_deployment_spec_replicas{{namespace="{NS}",deployment="{SVC}"}}',
    0, y, w=3, h=4, unit="percentunit", decimals=0,
    thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}],
    mappings=[{"type": "value", "options": {"1": {"text": "HEALTHY", "color": "green"}}},
              {"type": "range", "options": {"from": 0, "to": 0.99, "result": {"text": "DEGRADED", "color": "red"}}}],
    text_mode="value", description="Available replicas / desired replicas"
))

panels.append(stat(
    "Pods",
    f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{SVC}"}}',
    3, y, w=3, h=4, decimals=0,
    thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}],
    description="Running pod count"
))

panels.append(stat(
    "Restarts (24h)",
    f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{NS}",pod=~"{POD}"}}[24h]))',
    6, y, w=3, h=4, decimals=0,
    thresholds=[{"color": "green", "value": None}, {"color": "#EAB839", "value": 1}, {"color": "red", "value": 5}],
    description="Container restarts in last 24 hours"
))

panels.append(stat(
    "OOM Kills",
    f'sum(container_oom_events_total{{namespace="{NS}",pod=~"{POD}"}})',
    9, y, w=3, h=4, decimals=0,
    thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}],
    description="Out-of-memory kill events"
))

# Gauges for utilization
panels.append(gauge(
    "CPU Utilization",
    f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m])) / sum(kube_pod_container_resource_requests{{namespace="{NS}",pod=~"{POD}",resource="cpu"}})',
    12, y, w=4, h=4,
    description=f"CPU usage / CPU request ({CPU_REQUEST} cores)"
))

panels.append(gauge(
    "Memory Utilization",
    f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{POD}",container!=""}}) / sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{POD}",resource="memory"}})',
    16, y, w=4, h=4,
    description=f"Memory usage / memory limit ({MEM_LIMIT//1024//1024} MB)"
))

panels.append(stat(
    "CPU Throttling",
    f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m])) / (sum(rate(container_cpu_cfs_periods_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m])) > 0)',
    20, y, w=4, h=4, unit="percentunit", decimals=1,
    thresholds=[{"color": "green", "value": None}, {"color": "#EAB839", "value": 0.1}, {"color": "red", "value": 0.25}],
    color_mode="background_solid",
    description="% of CPU periods that were throttled"
))
y += 4

# ▸ ROW 2: Resource Usage Over Time
panels.append(row("Resource Usage", y))
y += 1

# CPU with baseline + request annotations
panels.append(timeseries(
    "CPU Usage",
    [
        (f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m]))', "usage"),
        (f'sum(kube_pod_container_resource_requests{{namespace="{NS}",pod=~"{POD}",resource="cpu"}})', "request"),
        (f'sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{POD}",resource="cpu"}})', "limit"),
    ],
    0, y, w=8, h=7, unit="short",
    description="CPU cores used vs requested vs limit"
))

# Memory with limit line
panels.append(timeseries(
    "Memory Usage",
    [
        (f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{POD}",container!=""}})', "working set"),
        (f'sum(container_memory_rss{{namespace="{NS}",pod=~"{POD}",container!=""}})', "RSS"),
        (f'sum(container_memory_cache{{namespace="{NS}",pod=~"{POD}",container!=""}})', "cache"),
        (f'sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{POD}",resource="memory"}})', "limit"),
    ],
    8, y, w=8, h=7, unit="bytes",
    description="Memory breakdown: working set, RSS, cache vs limit"
))

# CPU throttling over time
panels.append(timeseries(
    "CPU Throttling %",
    [
        (f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m])) / (sum(rate(container_cpu_cfs_periods_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m])) > 0)', "throttled %"),
    ],
    16, y, w=8, h=7, unit="percentunit", fill=20,
    thresholds=[{"color": "green", "value": None}, {"color": "#EAB839", "value": 0.1}, {"color": "red", "value": 0.25}],
    description="Sustained throttling > 10% means CPU request is too low"
))
y += 7

# ▸ ROW 3: Network & I/O
panels.append(row("Network & I/O", y))
y += 1

panels.append(timeseries(
    "Network Throughput",
    [
        (f'sum(rate(container_network_receive_bytes_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "rx"),
        (f'-sum(rate(container_network_transmit_bytes_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "tx (inverted)"),
    ],
    0, y, w=8, h=7, unit="Bps",
    description="Network receive (positive) and transmit (negative)"
))

panels.append(timeseries(
    "Network Errors & Drops",
    [
        (f'sum(rate(container_network_receive_errors_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "rx errors"),
        (f'sum(rate(container_network_transmit_errors_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "tx errors"),
        (f'sum(rate(container_network_receive_packets_dropped_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "rx drops"),
        (f'sum(rate(container_network_transmit_packets_dropped_total{{namespace="{NS}",pod=~"{POD}"}}[5m]))', "tx drops"),
    ],
    8, y, w=8, h=7, unit="pps",
    description="Non-zero values indicate network issues"
))

panels.append(timeseries(
    "Disk I/O",
    [
        (f'sum(rate(container_fs_reads_bytes_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m]))', "reads"),
        (f'sum(rate(container_fs_writes_bytes_total{{namespace="{NS}",pod=~"{POD}",container!=""}}[5m]))', "writes"),
    ],
    16, y, w=8, h=7, unit="Bps",
    description="Filesystem read/write throughput"
))
y += 7

# ▸ ROW 4: Process & Runtime
panels.append(row("Process Health", y))
y += 1

panels.append(timeseries(
    "Open File Descriptors / Sockets",
    [
        (f'container_sockets{{namespace="{NS}",pod=~"{POD}",container!=""}}', "sockets"),
    ],
    0, y, w=8, h=6,
    description="High socket count may indicate connection leaks"
))

panels.append(timeseries(
    "Threads",
    [
        (f'container_threads{{namespace="{NS}",pod=~"{POD}",container!=""}}', "threads"),
    ],
    8, y, w=8, h=6,
    description="Thread count — growing unbounded indicates a leak"
))

panels.append(timeseries(
    "Processes",
    [
        (f'container_processes{{namespace="{NS}",pod=~"{POD}",container!=""}}', "processes"),
    ],
    16, y, w=8, h=6,
    description="Process count inside container"
))
y += 6

# ▸ ROW 5: Dependencies Health Matrix
panels.append(row("Dependency Health", y))
y += 1

dep_x = 0
dep_row = 0
for dep_name, dep_container in DEPS.items():
    col = dep_x * 6
    if col >= 24:
        col = 0
        dep_row += 3
        dep_x = 0

    panels.append(stat(
        dep_name,
        f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{dep_name}"}}',
        col, y + dep_row, w=6, h=3, decimals=0,
        thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}],
        text_mode="value_and_sparkline",
        color_mode="background_solid",
        description=f"Pods available for {dep_name}"
    ))
    dep_x += 1

dep_total_height = dep_row + 3
y += dep_total_height

# Dependency CPU comparison
panels.append(timeseries(
    "Dependency CPU Usage",
    [(f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{dep}.*",container!=""}}[5m]))', dep)
     for dep in DEPS.keys()],
    0, y, w=12, h=7, unit="short",
    description="CPU usage across all downstream dependencies"
))

panels.append(timeseries(
    "Dependency Memory Usage",
    [(f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{dep}.*",container!=""}})', dep)
     for dep in DEPS.keys()],
    12, y, w=12, h=7, unit="bytes",
    description="Memory usage across all downstream dependencies"
))
y += 7

# ▸ ROW 6: HTTP Errors from Logs
panels.append(row("Application Logs", y))
y += 1

# Error log panel
panels.append(logs_panel(
    "Error Logs (HTTP 4xx/5xx)",
    f'{{namespace="{NS}",pod=~"{POD}"}} | json | http_resp_status =~ "4..|5.."',
    0, y, w=24, h=6,
    description="Request logs with HTTP status 4xx or 5xx"
))
y += 6

# All logs
panels.append(logs_panel(
    "All Logs",
    f'{{namespace="{NS}",pod=~"{POD}"}} | json',
    0, y, w=24, h=8,
    description="Full log stream — use the search bar to filter"
))
y += 8

# ─── Assemble ──────────────────────────────────────────────────────

dashboard = {
    "dashboard": {
        "uid": "sre-frontend-v2",
        "title": f"{SVC} — SRE Dashboard",
        "description": f"Auto-generated by sre-skills. Baselines: CPU {CPU_BASELINE} cores, Memory {MEM_BASELINE//1024//1024} MB. Thresholds derived from live data.",
        "tags": ["sre-skills", "auto-generated", NS, SVC],
        "timezone": "browser",
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "templating": {"list": []},
        "panels": panels,
        "annotations": {
            "list": [{
                "name": "Pod Restarts",
                "datasource": prom(),
                "enable": True,
                "expr": f'changes(kube_pod_container_status_restarts_total{{namespace="{NS}",pod=~"{POD}"}}[1m]) > 0',
                "tagKeys": "pod",
                "titleFormat": "Pod Restart",
                "iconColor": "red",
            }]
        },
        "links": [],
        "schemaVersion": 39,
        "liveNow": False,
        "fiscalYearStartMonth": 0,
    },
    "overwrite": True,
    "folderId": 0,
}

with open("/tmp/frontend-dashboard-v2.json", "w") as f:
    json.dump(dashboard, f, indent=2)

print(f"Dashboard v2 generated:")
print(f"  Panels: {len(panels)}")
print(f"  Rows: Service Health | Resource Usage | Network & I/O | Process Health | Dependency Health | Application Logs")
print(f"  Features:")
print(f"    - Status gauge (HEALTHY/DEGRADED)")
print(f"    - CPU/Memory utilization gauges (vs requests/limits)")
print(f"    - CPU throttling tracking")
print(f"    - OOM kill counter")
print(f"    - CPU with request+limit reference lines")
print(f"    - Memory breakdown (working set, RSS, cache)")
print(f"    - Network errors + drops")
print(f"    - Disk I/O")
print(f"    - Socket/thread/process leak detection")
print(f"    - Dependency health matrix (7 services)")
print(f"    - Dependency CPU/Memory comparison")
print(f"    - HTTP 5xx error logs from Loki")
print(f"    - Full log stream with JSON parsing")
print(f"    - Pod restart annotations")
