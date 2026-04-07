---
description: Discover infrastructure and build SRE context (.sre/)
allowed-tools: Bash, Read, Write
---

Run the `discover` skill to crawl Prometheus, Loki, and Kubernetes and populate the `.sre/` context directory.

Check for environment variables first:
- `PROMETHEUS_URL` — required
- `LOKI_URL` — optional, enables log discovery
- `GRAFANA_URL` — optional, enables dashboard registry
- `KUBECONFIG` — optional, enables Kubernetes topology discovery

If `PROMETHEUS_URL` is not set, ask the user for the URL.

Execute the full discover skill workflow (Phases 1-8). Report the discovery summary when complete.
