---
description: Investigate a service issue with live data
allowed-tools: Bash, Read, Write
model: opus
---

Run the `investigate` skill to diagnose a service issue using live Prometheus metrics, Loki logs, and `.sre/` context.

**Usage:** `/investigate <symptom description>`

Examples:
- `/investigate frontend latency spike`
- `/investigate cartservice pods crashing`
- `/investigate high error rate on checkoutservice`

If `.sre/` context exists, use it for baselines and topology. If not, fall back to direct Prometheus/Loki queries.

Execute the full investigation workflow and produce a structured investigation report.
