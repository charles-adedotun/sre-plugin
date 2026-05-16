# sre-plugin

Context-aware SRE tooling for Claude Code.

This plugin gives Claude Code slash commands, skills, and an SRE agent for Prometheus, Loki, Grafana, Kubernetes, dashboards, SLOs, alert tuning, and incident investigation. It uses a local `.sre/` directory as environment context so responses can reference discovered services, baselines, topology, logs, and dashboards instead of relying on generic runbooks.

The `.sre/` context is generated per target environment and should not contain credentials.

## Demo Evidence

The screenshots in `docs/screenshots/` were produced from a kind cluster running Google Online Boutique with kube-prometheus-stack and Loki. They demonstrate the expected dashboard shape and example data model, including a captured `cartservice` CrashLoopBackOff state.

This repository does not include an automated end-to-end test that starts that cluster or verifies live Prometheus, Loki, and Grafana responses. Treat the screenshots and `examples/` files as reproducible demo artifacts, not as a hosted service claim.

## What Is Included

- `.claude-plugin/plugin.json`: plugin metadata for local Claude Code installation.
- `commands/`: slash-command entrypoints for discovery, dashboard generation, investigation, SLOs, and alert tuning.
- `skills/`: detailed workflows consumed by those commands.
- `agents/sre.md`: multi-skill SRE agent prompt.
- `examples/sre/`: sample `.sre/` context files from an Online Boutique demo environment.
- `examples/dashboards/`: Python scripts used to generate the committed dashboard screenshots for the Online Boutique demo.
- `docs/screenshots/`: screenshots from that demo environment.

## Commands

| Command | Purpose |
| --- | --- |
| `/discover` | Build `.sre/` context from Prometheus, optional Loki, optional Grafana, and optional Kubernetes metadata. |
| `/dashboard <service>` | Generate Grafana dashboard JSON from discovered service context and baselines. |
| `/investigate <symptom>` | Correlate live metrics, logs, topology, and incident history for an operational symptom. |
| `/slo <service>` | Define or inspect SLOs and generate recording or alerting rule examples. |
| `/tune-alerts <service>` | Recommend alert thresholds from historical metric distributions and baselines. |

## Install Locally

Clone the plugin into Claude Code's local plugin cache:

```bash
git clone https://github.com/charles-adedotun/sre-plugin ~/sre-plugin
mkdir -p ~/.claude/plugins/cache/local/sre-skills/1.0.0
rsync -a --delete ~/sre-plugin/ ~/.claude/plugins/cache/local/sre-skills/1.0.0/
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

## Example Workflow

With live endpoints configured:

```bash
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100
export GRAFANA_URL=http://localhost:3000
export GRAFANA_PASSWORD=your-password
export GRAFANA_LOKI_UID=your-loki-uid
```

Run discovery, then investigate or build dashboards from the generated `.sre/` context:

```text
/discover
/dashboard frontend
/investigate cartservice pods crashing
```

For the committed Online Boutique demo context, an investigation for `cartservice pods crashing` has enough context to report:

```text
Investigation Report: cartservice - pods crashing

Current State vs Baseline
- Restarts: 10 total, about 10.07 per hour
- Memory: no current average because the container is not running
- Last known max memory: 127.6 MB

Likely finding
- cartservice is in CrashLoopBackOff, and frontend depends on cartservice.

Next checks
- Query Loki for recent cartservice error or panic logs.
- Check cartservice deployment events and recent image/config changes.
- Review frontend impact because it calls cartservice.
```

The same context lets `/dashboard frontend` build Grafana JSON using container metrics, kube-state metrics, topology dependencies, and Loki log panels when available.

## `.sre/` Context

Generated context is expected to live beside the user's application code:

```text
.sre/
|-- config.yaml
|-- topology.yaml
|-- services/
|-- baselines/
|-- incidents/
`-- dashboards.yaml
```

Credentials should stay in environment variables such as `GRAFANA_PASSWORD` or `GRAFANA_TOKEN`. Do not write tokens, passwords, kubeconfigs, or API keys into `.sre/config.yaml`.

## Quick Start

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

- Live accuracy depends on reachable Prometheus, Loki, Grafana, and Kubernetes data for the target environment.
- Example dashboard scripts are Online Boutique focused; the plugin workflow generalizes through discovered `.sre/` context.
- `/investigate` and the `sre` agent request Opus for multi-step reasoning; availability depends on the user's Claude Code configuration.
