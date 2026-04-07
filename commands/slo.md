---
description: Define SLOs or check error budget for a service
allowed-tools: Bash, Read, Write
---

Run the `define-slo` skill to define SLOs, calculate error budgets, or generate recording/alerting rules.

**Usage:** `/slo <service-name>`

If the service already has SLOs defined in `.sre/services/<name>.yaml`, show the current error budget status. Otherwise, guide the user through defining new SLOs.

Output Prometheus recording rule YAML and optional burn-rate alert rules.
