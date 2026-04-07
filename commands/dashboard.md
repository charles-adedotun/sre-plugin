---
description: Generate a Grafana dashboard for a service
allowed-tools: Bash, Read, Write
---

Generate a context-aware Grafana dashboard using the `dashboard` skill.

**Usage:** `/dashboard <service-name>`

If no service name is provided, list available services from `.sre/services/` and ask the user to choose.

If `.sre/` doesn't exist, tell the user to run `/discover` first.

Read the service context, baselines, and topology from `.sre/`, then execute the full dashboard skill workflow. Output the dashboard JSON and optionally push to Grafana if credentials are available.
