# sre-plugin

Claude Code plugin assets for SRE workflows with Prometheus, Loki, Grafana, and Kubernetes context.

The plugin defines commands, skills, and one SRE agent that use a local `.sre/` directory as environment context. The context files are generated per target environment and should not contain credentials.

## Current Contents

- `.claude-plugin/plugin.json`: plugin metadata for local Claude Code installation.
- `commands/`: slash-command entrypoints for discovery, dashboard generation, investigation, SLOs, and alert tuning.
- `skills/`: detailed workflows consumed by those commands.
- `agents/sre.md`: multi-skill SRE agent prompt.
- `examples/sre/`: sample `.sre/` context files from an Online Boutique demo environment.
- `examples/dashboards/`: Python scripts used to generate the committed dashboard screenshots for the Online Boutique demo.
- `docs/screenshots/`: screenshots from that demo environment.

## Demo Evidence

The screenshots in `docs/screenshots/` were produced from a kind cluster running Google Online Boutique with kube-prometheus-stack and Loki. They demonstrate the expected dashboard shape and example data model, including a captured `cartservice` CrashLoopBackOff state.

This repository does not include an automated end-to-end test that starts that cluster or verifies live Prometheus, Loki, and Grafana responses. Treat the screenshots and `examples/` files as reproducible demo artifacts, not as a hosted service claim.

## Commands

| Command | Purpose |
| --- | --- |
| `/discover` | Build `.sre/` context from Prometheus, optional Loki, optional Grafana, and optional Kubernetes metadata. |
| `/dashboard <service>` | Generate Grafana dashboard JSON from discovered service context and baselines. |
| `/investigate <symptom>` | Correlate live metrics, logs, topology, and incident history for an operational symptom. |
| `/slo <service>` | Define or inspect SLOs and generate recording or alerting rule examples. |
| `/tune-alerts <service>` | Recommend alert thresholds from historical metric distributions and baselines. |

## `.sre/` Context

Generated context is expected to live beside the user's application code:

```text
.sre/
├── config.yaml
├── topology.yaml
├── services/
├── baselines/
├── incidents/
└── dashboards.yaml
```

Credentials should stay in environment variables such as `GRAFANA_PASSWORD` or `GRAFANA_TOKEN`. Do not write tokens, passwords, kubeconfigs, or API keys into `.sre/config.yaml`.

## Install Locally

```bash
git clone https://github.com/charles-adedotun/sre-plugin ~/sre-plugin
mkdir -p ~/.claude/plugins/cache/local/sre-skills/1.0.0
cp -r ~/sre-plugin/. ~/.claude/plugins/cache/local/sre-skills/1.0.0/
```

Then register the local plugin in `~/.claude/plugins/installed_plugins.json`:

```json
"sre-skills@local": [
  {
    "scope": "user",
    "installPath": "/Users/YOUR_USERNAME/.claude/plugins/cache/local/sre-skills/1.0.0",
    "version": "1.0.0",
    "installedAt": "2026-01-01T00:00:00.000Z",
    "lastUpdated": "2026-01-01T00:00:00.000Z"
  }
]
```

Restart Claude Code after registration.

## Quick Start

```bash
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100
export GRAFANA_URL=http://localhost:3000
export GRAFANA_PASSWORD=your-password
export GRAFANA_LOKI_UID=your-loki-uid
```

In Claude Code:

```text
/discover
/dashboard frontend
/investigate "high error rate"
/slo payment-service
/tune-alerts cartservice
```

## Verification

Run the local validation script:

```bash
python3 scripts/validate_plugin.py
```

The CI workflow runs the same script. It validates plugin metadata, command and skill frontmatter, example config safety, and Python syntax for the dashboard generator scripts.

## Known Limits

- Live Prometheus, Loki, Grafana, and Kubernetes behavior depends on the user's environment.
- The dashboard generator scripts in `examples/dashboards/` default to Online Boutique names and are examples, not a general dashboard engine.
- `/investigate` and the `sre` agent request Opus for multi-step operational reasoning; access depends on the user's Claude Code configuration.
