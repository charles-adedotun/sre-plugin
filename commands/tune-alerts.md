---
description: Tune alerting thresholds using baseline data for a service
allowed-tools: Bash, Read, Write
---

Run the `tune-alerts` skill to calculate data-driven alerting thresholds using historical metric distributions from `.sre/baselines/`.

**Usage:** `/tune-alerts <service-name>`

Analyzes the last 7 days of metrics (using `quantile_over_time` and `stddev_over_time`) to recommend CPU, memory, and restart thresholds that minimize false positives while catching real incidents.

Output: ready-to-apply Prometheus alert rule YAML.
