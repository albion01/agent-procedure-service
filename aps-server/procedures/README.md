# APS Procedure Library

Pre-built APS procedure records for common use cases. Import into your APS instance
to get immediate protection and compliance scanning capabilities.

## Use Cases

### Supply Chain Protection (`supply-chain/`)

Protects against compromised packages, container images, and CI/CD actions.
Four advisory registries plus automated CVE scanning via OSV.dev.

**What's included:**

| File | Description |
|------|-------------|
| `npm-supply-chain.json` | APS record — blocks compromised npm packages |
| `pypi-supply-chain.json` | APS record — blocks compromised PyPI packages |
| `docker-supply-chain.json` | APS record — blocks compromised Docker images |
| `github-actions-supply-chain.json` | APS record — blocks compromised GitHub Actions |
| `cve-scanner.json` | APS record — OSV.dev CVE scanning for installed packages |
| `advisories/npm-advisories.json` | Known compromised npm packages (axios, nx, chalk, debug) |
| `advisories/pypi-advisories.json` | Known compromised PyPI packages (litellm, ultralytics) |
| `advisories/docker-advisories.json` | Known compromised Docker images (aquasec/trivy) |
| `advisories/github-actions-advisories.json` | Known compromised GitHub Actions (tj-actions, reviewdog, trivy-action) |
| `hooks/cve-check.py` | CVE scanner script — queries OSV.dev API |

**Quick start:**

1. Import APS records into your platform:
   ```bash
   for f in supply-chain/*.json; do
     curl -X POST http://YOUR_APS_SERVER/api/v1/aps/ \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d @"$f"
   done
   ```

2. Copy advisory files to your hooks directory:
   ```bash
   cp supply-chain/advisories/*.json ~/.claude/hooks/
   ```

3. Copy the CVE scanner:
   ```bash
   cp supply-chain/hooks/cve-check.py ~/.claude/hooks/
   chmod +x ~/.claude/hooks/cve-check.py
   ```

4. Add to your Claude Code `settings.json` hook (see `supply-chain/hook-config-example.json`).

5. Add a daily cron for scheduled CVE scanning:
   ```bash
   0 6 * * * python3 ~/.claude/hooks/cve-check.py --scan-log --create-findings
   ```

**Updating advisories:**

When new supply chain attacks are discovered, add entries to the appropriate
advisory JSON file. No code changes needed — the hook reads the files at runtime.

## Creating Your Own Procedures

Each procedure JSON follows this schema:

```json
{
  "service_name": "unique-identifier",
  "display_name": "Human-Readable Name",
  "url": "http://your-platform/api/v1",
  "service_type": "scan|workflow|registry|api",
  "auth_method": "jwt|api-token|none",
  "procedure_steps": ["Step 1: ...", "Step 2: ..."],
  "restrictions": ["Read-only", "Do not modify systems"],
  "change_record_required": false,
  "allowed_agents": ["auditor", "ciso"],
  "tags": ["category", "subcategory"],
  "is_active": true,
  "notes": "Additional context"
}
```

Import with `POST /api/v1/aps/` — the `service_name` must be unique.

## Contributing

Add new procedure files via pull request. Include:
- The procedure JSON
- A brief description in this README
- For advisory files: source references for each entry
