#!/usr/bin/env python3
"""Generate all SRE dashboards: Logs Explorer, Cluster Overview, per-service.

Environment variables:
  GRAFANA_PROM_UID   Prometheus datasource UID (default: "prometheus")
  GRAFANA_LOKI_UID   Loki datasource UID — find it in Grafana > Connections > Data sources
  SRE_NAMESPACE      Kubernetes namespace to monitor (default: "online-boutique")
  SRE_OUT_DIR        Output directory for dashboard JSON (default: /tmp/dashboards)
"""
import json, os

PROM_UID = os.environ.get("GRAFANA_PROM_UID", "prometheus")
LOKI_UID = os.environ.get("GRAFANA_LOKI_UID", "")
NS = os.environ.get("SRE_NAMESPACE", "online-boutique")
OUT_DIR = os.environ.get("SRE_OUT_DIR", "/tmp/dashboards")

if not LOKI_UID:
    print("WARNING: GRAFANA_LOKI_UID not set. Log panels will show 'No data' on other Grafana instances.")
    print("  Find your Loki UID: Grafana → Connections → Data sources → Loki → copy UID from URL")
    print("  Then set: export GRAFANA_LOKI_UID=<your-uid>")
    LOKI_UID = "CHANGE-ME-SEE-WARNING-ABOVE"

os.makedirs(OUT_DIR, exist_ok=True)

_id = 0
def nid():
    global _id; _id += 1; return _id

def prom(): return {"type": "prometheus", "uid": PROM_UID}
def loki(): return {"type": "loki", "uid": LOKI_UID}

def var(name, query, ds_type="prometheus", ds_uid=PROM_UID, label=None, include_all=False, current=None, multi=False):
    v = {
        "name": name,
        "label": label or name,
        "type": "query",
        "datasource": {"type": ds_type, "uid": ds_uid},
        "query": query,
        "refresh": 2,
        "sort": 1,
        "includeAll": include_all,
        "multi": multi,
    }
    if current:
        v["current"] = {"text": current, "value": current}
    return v

def custom_var(name, values, label=None, include_all=False, multi=False, current=None):
    return {
        "name": name,
        "label": label or name,
        "type": "custom",
        "query": ",".join(values),
        "current": {"text": current or values[0], "value": current or values[0]},
        "includeAll": include_all,
        "multi": multi,
        "options": [{"text": v, "value": v, "selected": v == (current or values[0])} for v in values],
    }

def row(title, y, collapsed=False):
    return {"id": nid(), "type": "row", "title": title, "gridPos": {"x":0,"y":y,"w":24,"h":1}, "collapsed": collapsed, "panels": []}

def stat(title, expr, x, y, w=6, h=3, unit="short", thresholds=None, decimals=None, color_mode="background_solid", ds=None, description=""):
    t = thresholds or [{"color":"green","value":None}]
    p = {
        "id": nid(), "type": "stat", "title": title, "description": description,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": ds or prom(),
        "targets": [{"expr": expr, "refId": "A", "instant": True}],
        "fieldConfig": {"defaults": {"unit": unit, "thresholds": {"mode":"absolute","steps":t}, "color": {"mode":"thresholds"}, "mappings":[]}, "overrides":[]},
        "options": {"colorMode": color_mode, "graphMode": "area", "textMode": "value_and_sparkline", "justifyMode": "center", "reduceOptions": {"calcs":["lastNotNull"]}},
    }
    if decimals is not None: p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p

def gauge(title, expr, x, y, w=4, h=5, unit="percentunit", thresholds=None):
    t = thresholds or [{"color":"green","value":None},{"color":"#EAB839","value":0.7},{"color":"red","value":0.9}]
    return {
        "id": nid(), "type": "gauge", "title": title,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": prom(),
        "targets": [{"expr": expr, "refId": "A", "instant": True}],
        "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": 1, "thresholds": {"mode":"absolute","steps":t}, "color": {"mode":"thresholds"}}, "overrides":[]},
        "options": {"reduceOptions": {"calcs":["lastNotNull"]}, "showThresholdLabels": False, "showThresholdMarkers": True},
    }

def ts(title, targets, x, y, w=12, h=7, unit="short", fill=10, stack=False, thresholds=None, legend="bottom", description="", ds=None):
    tgts = [{"expr":t[0],"legendFormat":t[1],"refId":chr(65+i)} for i,t in enumerate(targets)]
    return {
        "id": nid(), "type": "timeseries", "title": title, "description": description,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": ds or prom(),
        "targets": tgts,
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"drawStyle":"line","lineInterpolation":"smooth","lineWidth":2,"fillOpacity":fill,"showPoints":"never","spanNulls":True,"stacking":{"mode":"normal" if stack else "none"},"thresholdsStyle":{"mode":"dashed" if thresholds else "off"}},"color":{"mode":"palette-classic-by-name"},"thresholds":{"mode":"absolute","steps":thresholds or [{"color":"green","value":None}]}}, "overrides":[]},
        "options": {"legend": {"displayMode":"list","placement":legend,"calcs":["mean","max"] if legend=="bottom" else []},"tooltip":{"mode":"multi","sort":"desc"}},
    }

def bar(title, targets, x, y, w=12, h=7, unit="short", stack=True, ds=None):
    tgts = [{"expr":t[0],"legendFormat":t[1],"refId":chr(65+i)} for i,t in enumerate(targets)]
    return {
        "id": nid(), "type": "barchart", "title": title,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": ds or prom(),
        "targets": tgts,
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode":"palette-classic-by-name"}}, "overrides":[]},
        "options": {"orientation": "horizontal", "showValue": "auto", "stacking": "normal" if stack else "none", "legend": {"displayMode":"list","placement":"right"}},
    }

def logs_panel(title, expr, x, y, w=24, h=10, description=""):
    return {
        "id": nid(), "type": "logs", "title": title, "description": description,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": loki(),
        "targets": [{"expr": expr, "refId": "A", "queryType": "range"}],
        "options": {"showTime":True,"showLabels":True,"showCommonLabels":False,"wrapLogMessage":True,"prettifyLogMessage":True,"enableLogDetails":True,"sortOrder":"Descending","dedupStrategy":"none"},
    }

def text_panel(content, x, y, w=24, h=2):
    return {"id": nid(), "type": "text", "gridPos": {"x":x,"y":y,"w":w,"h":h}, "options": {"content": content, "mode": "markdown"}}

def loki_ts(title, expr, x, y, w=12, h=7, unit="short", legend="bottom", stack=False, fill=10):
    """Timeseries panel using Loki as datasource (for metric queries over logs)."""
    return {
        "id": nid(), "type": "timeseries", "title": title,
        "gridPos": {"x":x,"y":y,"w":w,"h":h},
        "datasource": loki(),
        "targets": [{"expr": expr, "refId": "A", "queryType": "range"}],
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"drawStyle":"bars" if not stack else "line","lineWidth":1,"fillOpacity":fill if not stack else 30,"showPoints":"never","stacking":{"mode":"normal" if stack else "none"}},"color":{"mode":"palette-classic-by-name"}}, "overrides":[]},
        "options": {"legend":{"displayMode":"list","placement":legend},"tooltip":{"mode":"multi","sort":"desc"}},
    }

# ═══════════════════════════════════════════════════════════════════
# DASHBOARD 1: LOGS EXPLORER
# ═══════════════════════════════════════════════════════════════════

def build_logs_dashboard():
    global _id; _id = 0
    panels = []
    y = 0

    variables = [
        var("service", f'label_values(kube_deployment_spec_replicas{{namespace="{NS}"}}, deployment)',
            label="Service", include_all=True, multi=True, current="frontend"),
        custom_var("severity", ["debug","info","warn","warning","error","fatal","panic"],
                   label="Severity", include_all=True, multi=True, current="All"),
        custom_var("status_min", ["0","200","400","500"], label="HTTP Status >=", current="0"),
        custom_var("method", ["GET","POST","PUT","DELETE","PATCH"], label="Method", include_all=True, multi=True, current="All"),
    ]

    # ── Row: Log Volume Overview
    panels.append(row("Log Volume", y)); y += 1

    # Log rate by service (stacked area)
    panels.append(loki_ts(
        "Log Rate by Service",
        f'sum by (pod) (rate({{namespace="{NS}", pod=~"$service.*"}} [1m]))',
        0, y, w=12, h=7, stack=True, fill=40,
    ))

    # Log rate by severity
    panels.append(loki_ts(
        "Log Rate by Severity",
        f'sum by (severity) (rate({{namespace="{NS}", pod=~"$service.*"}} | json | severity=~"$severity" [1m]))',
        12, y, w=12, h=7, stack=True, fill=40,
    ))
    y += 7

    # ── Row: HTTP Analysis (frontend-specific but works for any service with HTTP logs)
    panels.append(row("HTTP Analysis", y)); y += 1

    # HTTP status code distribution over time
    panels.append(loki_ts(
        "HTTP Status Codes Over Time",
        f'sum by (http_resp_status) (rate({{namespace="{NS}", app=~"$service"}} | json | http_resp_status != "" [1m]))',
        0, y, w=8, h=7, stack=True, fill=30,
    ))

    # Error rate (5xx)
    panels.append(loki_ts(
        "5xx Error Rate",
        f'sum(rate({{namespace="{NS}", app=~"$service"}} | json | http_resp_status =~ "5.." [1m]))',
        8, y, w=8, h=7, fill=20,
    ))

    # Latency from logs (p99 via quantile_over_time won't work in LogQL, so show distribution)
    panels.append(loki_ts(
        "Response Time (from logs)",
        f'avg by (http_req_method) (avg_over_time({{namespace="{NS}", pod=~"$service.*"}} | json | http_resp_took_ms != "" | unwrap http_resp_took_ms [1m]))',
        16, y, w=8, h=7, unit="ms",
    ))
    y += 7

    # ── Row: Top Errors
    panels.append(row("Error Analysis", y)); y += 1

    # Error logs with context
    panels.append(logs_panel(
        "Error Logs",
        f'{{namespace="{NS}", app=~"$service"}} | json | severity=~"error|fatal|panic|warn|warning" or http_resp_status =~ "5.."',
        0, y, w=24, h=8,
        description="Filtered by severity (error/fatal/panic/warn) OR HTTP 5xx status"
    ))
    y += 8

    # ── Row: Request Tracing
    panels.append(row("Request Explorer", y)); y += 1

    # Slow requests
    panels.append(logs_panel(
        "Slow Requests (> 100ms)",
        f'{{namespace="{NS}", pod=~"$service.*"}} | json | http_resp_took_ms > 100',
        0, y, w=12, h=8,
        description="Requests taking longer than 100ms — may indicate downstream latency"
    ))

    # Specific path filter
    panels.append(logs_panel(
        "Requests by Method ($method)",
        f'{{namespace="{NS}", pod=~"$service.*"}} | json | http_req_method=~"$method"',
        12, y, w=12, h=8,
        description="Filter by HTTP method using the variable selector above"
    ))
    y += 8

    # ── Row: Full Log Stream
    panels.append(row("Full Log Stream", y)); y += 1

    panels.append(logs_panel(
        "All Logs",
        f'{{namespace="{NS}", pod=~"$service.*"}} | json',
        0, y, w=24, h=12,
        description="Full log stream — use Grafana's built-in search bar and label filters to drill down"
    ))
    y += 12

    return {
        "dashboard": {
            "uid": "sre-logs",
            "title": "Logs Explorer — SRE",
            "description": "Interactive log exploration with service, severity, status code, and method filters.",
            "tags": ["sre-skills", "logs", NS],
            "timezone": "browser",
            "refresh": "10s",
            "time": {"from": "now-30m", "to": "now"},
            "templating": {"list": variables},
            "panels": panels,
            "annotations": {"list": []},
            "schemaVersion": 39,
        },
        "overwrite": True, "folderId": 0,
    }


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD 2: CLUSTER OVERVIEW
# ═══════════════════════════════════════════════════════════════════

def build_cluster_overview():
    global _id; _id = 0
    panels = []
    y = 0

    SERVICES = ["frontend","checkoutservice","cartservice","paymentservice","currencyservice",
                "productcatalogservice","shippingservice","emailservice","recommendationservice","adservice","redis-cart"]

    panels.append(text_panel(
        f"# Online Boutique — Cluster Overview\n"
        f"**{len(SERVICES)} services** in namespace `{NS}` · Load generator active · "
        f"[Logs Explorer](/d/sre-logs) · [Frontend Dashboard](/d/sre-frontend-v2)",
        0, y, 24, 2
    ))
    y += 2

    # ── Row: Cluster totals
    panels.append(row("Cluster Health", y)); y += 1

    panels.append(stat("Total Pods Running",
        f'count(kube_pod_status_phase{{namespace="{NS}",phase="Running"}})',
        0, y, w=4, h=4, decimals=0,
        thresholds=[{"color":"red","value":None},{"color":"#EAB839","value":10},{"color":"green","value":12}]
    ))
    panels.append(stat("Total Restarts (1h)",
        f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{NS}"}}[1h]))',
        4, y, w=4, h=4, decimals=0,
        thresholds=[{"color":"green","value":None},{"color":"#EAB839","value":1},{"color":"red","value":5}]
    ))
    panels.append(stat("OOM Events",
        f'sum(container_oom_events_total{{namespace="{NS}"}})',
        8, y, w=4, h=4, decimals=0,
        thresholds=[{"color":"green","value":None},{"color":"red","value":1}]
    ))
    panels.append(gauge("Total CPU Utilization",
        f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",container!=""}}[5m])) / sum(kube_pod_container_resource_requests{{namespace="{NS}",resource="cpu"}})',
        12, y, w=4, h=4
    ))
    panels.append(gauge("Total Memory Utilization",
        f'sum(container_memory_working_set_bytes{{namespace="{NS}",container!=""}}) / sum(kube_pod_container_resource_limits{{namespace="{NS}",resource="memory"}})',
        16, y, w=4, h=4
    ))
    panels.append(stat("Log Errors (5m)",
        f'sum(count_over_time({{namespace="{NS}"}} | json | severity="error" [5m]))',
        20, y, w=4, h=4, decimals=0, ds=loki(),
        thresholds=[{"color":"green","value":None},{"color":"#EAB839","value":10},{"color":"red","value":50}]
    ))
    y += 4

    # ── Row: Service Health Matrix
    panels.append(row("Service Health Matrix", y)); y += 1

    # Stat panel per service (4 columns x 3 rows = 12 services)
    for i, svc in enumerate(SERVICES):
        col = (i % 4) * 6
        r = (i // 4) * 3
        panels.append(stat(
            svc,
            f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{svc}"}}',
            col, y + r, w=6, h=3, decimals=0,
            thresholds=[{"color":"red","value":None},{"color":"green","value":1}],
            color_mode="background_solid"
        ))
    y += ((len(SERVICES) - 1) // 4 + 1) * 3

    # ── Row: CPU comparison
    panels.append(row("Resource Comparison", y)); y += 1

    panels.append(ts(
        "CPU Usage by Service",
        [(f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{s}.*",container!=""}}[5m]))', s) for s in SERVICES],
        0, y, w=12, h=8, unit="short",
        description="Compare CPU usage across all services"
    ))
    panels.append(ts(
        "Memory Usage by Service",
        [(f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{s}.*",container!=""}})', s) for s in SERVICES],
        12, y, w=12, h=8, unit="bytes",
        description="Compare memory usage across all services"
    ))
    y += 8

    # ── Row: Restarts & Stability
    panels.append(row("Stability", y)); y += 1

    panels.append(ts(
        "Restart Rate by Service",
        [(f'rate(kube_pod_container_status_restarts_total{{namespace="{NS}",pod=~"{s}.*"}}[5m])', s) for s in SERVICES],
        0, y, w=12, h=7,
        description="Non-zero restart rate indicates instability"
    ))
    panels.append(ts(
        "CPU Throttling by Service",
        [(f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{NS}",pod=~"{s}.*",container!=""}}[5m])) / (sum(rate(container_cpu_cfs_periods_total{{namespace="{NS}",pod=~"{s}.*",container!=""}}[5m])) > 0)', s) for s in SERVICES],
        12, y, w=12, h=7, unit="percentunit",
        description="Services being throttled — may need higher CPU requests"
    ))
    y += 7

    # ── Row: Network
    panels.append(row("Network Overview", y)); y += 1

    panels.append(ts(
        "Network Receive by Service",
        [(f'sum(rate(container_network_receive_bytes_total{{namespace="{NS}",pod=~"{s}.*"}}[5m]))', s) for s in SERVICES],
        0, y, w=12, h=7, unit="Bps"
    ))
    panels.append(ts(
        "Network Transmit by Service",
        [(f'sum(rate(container_network_transmit_bytes_total{{namespace="{NS}",pod=~"{s}.*"}}[5m]))', s) for s in SERVICES],
        12, y, w=12, h=7, unit="Bps"
    ))
    y += 7

    return {
        "dashboard": {
            "uid": "sre-cluster",
            "title": "Cluster Overview — SRE",
            "description": "All services at a glance: health, resources, stability.",
            "tags": ["sre-skills", "cluster", NS],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {"list": []},
            "panels": panels,
            "annotations": {"list": [{
                "name": "Pod Restarts",
                "datasource": prom(),
                "enable": True,
                "expr": f'changes(kube_pod_container_status_restarts_total{{namespace="{NS}"}}[1m]) > 0',
                "tagKeys": "pod",
                "titleFormat": "Restart: {{pod}}",
                "iconColor": "red",
            }]},
            "links": [
                {"title": "Logs Explorer", "url": "/d/sre-logs", "type": "link", "icon": "doc"},
                {"title": "Frontend", "url": "/d/sre-frontend-v2", "type": "link", "icon": "dashboard"},
            ],
            "schemaVersion": 39,
        },
        "overwrite": True, "folderId": 0,
    }


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD 3-5: PER-SERVICE (checkoutservice, cartservice, adservice)
# ═══════════════════════════════════════════════════════════════════

BASELINES = {
    "checkoutservice": {"cpu": 0.001, "cpu_req": 0.1, "mem": 20971520, "mem_limit": 134217728, "deps": ["productcatalogservice","shippingservice","paymentservice","emailservice","currencyservice","cartservice"]},
    "cartservice":     {"cpu": 0.045, "cpu_req": 0.2, "mem": 86000000, "mem_limit": 134217728, "deps": ["redis-cart"]},
    "adservice":       {"cpu": 0.007, "cpu_req": 0.2, "mem": 232000000, "mem_limit": 314572800, "deps": []},
}

def build_service_dashboard(svc, info):
    global _id; _id = 0
    panels = []
    y = 0
    pod = f"{svc}.*"
    deps = info["deps"]

    panels.append(text_panel(
        f"# {svc}\n**Namespace:** `{NS}` · **CPU Request:** {info['cpu_req']} · "
        f"**Memory Limit:** {info['mem_limit']//1024//1024} MB · "
        f"**Dependencies:** {', '.join(deps) if deps else 'none'} · "
        f"[Cluster Overview](/d/sre-cluster) · [Logs](/d/sre-logs)",
        0, y, 24, 2
    ))
    y += 2

    # ── Health
    panels.append(row("Service Health", y)); y += 1

    panels.append(stat("Status",
        f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{svc}"}} / kube_deployment_spec_replicas{{namespace="{NS}",deployment="{svc}"}}',
        0, y, w=3, h=4, unit="percentunit", decimals=0,
        thresholds=[{"color":"red","value":None},{"color":"green","value":1}]
    ))
    panels.append(stat("Pods", f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{svc}"}}',
        3, y, w=3, h=4, decimals=0, thresholds=[{"color":"red","value":None},{"color":"green","value":1}]))
    panels.append(stat("Restarts (24h)", f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{NS}",pod=~"{pod}"}}[24h]))',
        6, y, w=3, h=4, decimals=0, thresholds=[{"color":"green","value":None},{"color":"#EAB839","value":1},{"color":"red","value":5}]))
    panels.append(stat("OOM Kills", f'sum(container_oom_events_total{{namespace="{NS}",pod=~"{pod}"}})',
        9, y, w=3, h=4, decimals=0, thresholds=[{"color":"green","value":None},{"color":"red","value":1}]))
    panels.append(gauge("CPU Util",
        f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m])) / sum(kube_pod_container_resource_requests{{namespace="{NS}",pod=~"{pod}",resource="cpu"}})',
        12, y, w=4, h=4))
    panels.append(gauge("Memory Util",
        f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{pod}",container!=""}}) / sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{pod}",resource="memory"}})',
        16, y, w=4, h=4))
    panels.append(stat("Throttling",
        f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m])) / sum(rate(container_cpu_cfs_periods_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m]))',
        20, y, w=4, h=4, unit="percentunit", decimals=1,
        thresholds=[{"color":"green","value":None},{"color":"#EAB839","value":0.1},{"color":"red","value":0.25}]))
    y += 4

    # ── Resources
    panels.append(row("Resource Usage", y)); y += 1

    panels.append(ts("CPU Usage", [
        (f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m]))', "usage"),
        (f'sum(kube_pod_container_resource_requests{{namespace="{NS}",pod=~"{pod}",resource="cpu"}})', "request"),
        (f'sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{pod}",resource="cpu"}})', "limit"),
    ], 0, y, w=8, h=7))

    panels.append(ts("Memory Usage", [
        (f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{pod}",container!=""}})', "working set"),
        (f'sum(container_memory_rss{{namespace="{NS}",pod=~"{pod}",container!=""}})', "RSS"),
        (f'sum(container_memory_cache{{namespace="{NS}",pod=~"{pod}",container!=""}})', "cache"),
        (f'sum(kube_pod_container_resource_limits{{namespace="{NS}",pod=~"{pod}",resource="memory"}})', "limit"),
    ], 8, y, w=8, h=7, unit="bytes"))

    panels.append(ts("CPU Throttling %", [
        (f'sum(rate(container_cpu_cfs_throttled_periods_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m])) / sum(rate(container_cpu_cfs_periods_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m]))', "throttled %"),
    ], 16, y, w=8, h=7, unit="percentunit", fill=20,
    thresholds=[{"color":"green","value":None},{"color":"#EAB839","value":0.1},{"color":"red","value":0.25}]))
    y += 7

    # ── Network
    panels.append(row("Network & I/O", y)); y += 1

    panels.append(ts("Network Throughput", [
        (f'sum(rate(container_network_receive_bytes_total{{namespace="{NS}",pod=~"{pod}"}}[5m]))', "rx"),
        (f'-sum(rate(container_network_transmit_bytes_total{{namespace="{NS}",pod=~"{pod}"}}[5m]))', "tx"),
    ], 0, y, w=8, h=7, unit="Bps"))

    panels.append(ts("Network Errors", [
        (f'sum(rate(container_network_receive_errors_total{{namespace="{NS}",pod=~"{pod}"}}[5m]))', "rx errors"),
        (f'sum(rate(container_network_transmit_errors_total{{namespace="{NS}",pod=~"{pod}"}}[5m]))', "tx errors"),
    ], 8, y, w=8, h=7, unit="pps"))

    panels.append(ts("Disk I/O", [
        (f'sum(rate(container_fs_reads_bytes_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m]))', "reads"),
        (f'sum(rate(container_fs_writes_bytes_total{{namespace="{NS}",pod=~"{pod}",container!=""}}[5m]))', "writes"),
    ], 16, y, w=8, h=7, unit="Bps"))
    y += 7

    # ── Dependencies (if any)
    if deps:
        panels.append(row("Dependencies", y)); y += 1
        for i, dep in enumerate(deps):
            col = (i % 4) * 6
            r = (i // 4) * 3
            panels.append(stat(dep,
                f'kube_deployment_status_replicas_available{{namespace="{NS}",deployment="{dep}"}}',
                col, y + r, w=6, h=3, decimals=0,
                thresholds=[{"color":"red","value":None},{"color":"green","value":1}],
                color_mode="background_solid"))
        y += ((len(deps)-1)//4 + 1) * 3

        panels.append(ts("Dependency CPU", [
            (f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NS}",pod=~"{d}.*",container!=""}}[5m]))', d) for d in deps
        ], 0, y, w=12, h=7))
        panels.append(ts("Dependency Memory", [
            (f'sum(container_memory_working_set_bytes{{namespace="{NS}",pod=~"{d}.*",container!=""}})', d) for d in deps
        ], 12, y, w=12, h=7, unit="bytes"))
        y += 7

    # ── Logs
    panels.append(row("Logs", y)); y += 1

    panels.append(logs_panel(
        "Error & Warning Logs",
        f'{{namespace="{NS}", pod=~"{pod}"}} | json | severity=~"error|warn|warning|fatal"',
        0, y, w=24, h=8
    ))
    y += 8

    uid = f"sre-{svc}"
    return {
        "dashboard": {
            "uid": uid,
            "title": f"{svc} — SRE Dashboard",
            "tags": ["sre-skills", "auto-generated", NS, svc],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {"list": []},
            "panels": panels,
            "annotations": {"list": [{"name":"Restarts","datasource":prom(),"enable":True,
                "expr":f'changes(kube_pod_container_status_restarts_total{{namespace="{NS}",pod=~"{pod}"}}[1m]) > 0',
                "tagKeys":"pod","titleFormat":"Restart","iconColor":"red"}]},
            "links": [
                {"title": "Cluster Overview", "url": "/d/sre-cluster", "type": "link"},
                {"title": "Logs Explorer", "url": "/d/sre-logs", "type": "link"},
            ],
            "schemaVersion": 39,
        },
        "overwrite": True, "folderId": 0,
    }


# ═══════════════════════════════════════════════════════════════════
# GENERATE ALL
# ═══════════════════════════════════════════════════════════════════

dashboards = {
    "logs-explorer": build_logs_dashboard(),
    "cluster-overview": build_cluster_overview(),
}
for svc, info in BASELINES.items():
    dashboards[svc] = build_service_dashboard(svc, info)

for name, dash in dashboards.items():
    path = f"{OUT_DIR}/{name}.json"
    with open(path, "w") as f:
        json.dump(dash, f, indent=2)
    panel_count = len(dash["dashboard"]["panels"])
    print(f"  {name:25s} → {path} ({panel_count} panels)")

print(f"\nGenerated {len(dashboards)} dashboards.")
