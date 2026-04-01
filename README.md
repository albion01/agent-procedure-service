# Agent Procedure Service (APS)

**A standalone protocol and server for publishing machine-readable instructions that tell AI agents how to interact with services.**

APS is to service interaction what DNS is to name resolution. DNS tells agents *where* a service is. APS tells agents *how* to use it.

---

## The Problem

AI agents are the new network clients. They authenticate to APIs, execute commands, and interact with services autonomously. But nobody tells them *how*:

- **Documentation** is written for humans, not machines
- **robots.txt** says what NOT to do, not how to do things correctly
- **OpenAPI/Swagger** describes API shape, not authentication procedures or operational restrictions
- **Agent memory** is unreliable — context windows compress, instructions get lost

The result: agents guess, retry, leak credentials, and generate junk traffic. Service operators get hammered. Agent operators get errors.

## The Solution

APS is a standalone server — like a DNS server — that publishes structured procedure records for services. Any agent can query it. Any organization can run one.

```
Agent: GET /resolve/freeipa?scope=certs

APS returns:
{
  "service": "freeipa",
  "display_name": "FreeIPA — Certificate Authority",
  "procedure": [
    "Generate CSR: openssl req -new -newkey rsa:2048 ...",
    "Submit via JSON-RPC: {\"method\": \"cert_request\", ...}",
    "Save the signed cert from the response",
    "Create a change record documenting the cert"
  ],
  "restrictions": [
    "ONLY perform operations in this record",
    "NEVER self-sign certificates",
    "NEVER issue without explicit user instruction"
  ]
}
```

The agent gets exact instructions. No guessing. No retrying. No reading config files for passwords.

## Key Properties

- **Public** — No authentication needed to read procedures. Like DNS, free to query.
- **Standalone** — No dependencies on other services. Works if everything else is down.
- **Scoped** — Procedures are scoped by operation type (certs, users, DNS). Agents see only what's relevant. Least Functionality applied to agent knowledge.
- **Open** — JSON over HTTP. All standards are free and open (RFC 2104, RFC 8259, FIPS 180-4).
- **Agent-agnostic** — Works with Claude, GPT, Gemini, Llama, Qwen, or any future model. The procedures are plain language instructions any LLM can follow.
- **Delegation-aware** — Procedures can route work to the right model: "Don't do this yourself. Hand it to the internal model at ollama:11434."

## Incentives

| For service operators | For agent operators |
|----------------------|-------------------|
| Fewer malformed requests | Correct auth on first try |
| Less wasted bandwidth | Fewer errors and retries |
| Agents follow your rules | Clear operational boundaries |
| Publish once, all agents benefit | Query once, procedure is cached |

## Agentic Procedural Controls (APCs)

APS introduces a new security control category designed for AI agents:

| Control Type | Target | Mechanism |
|-------------|--------|-----------|
| Technical | Systems | Enforcement (firewalls, ACLs) |
| Administrative | Humans | Policy and training |
| Physical | Humans | Barriers and deterrence |
| **Agentic Procedural** | **AI Agents** | **Machine-readable instructions at the point of action** |

APCs work because agents reliably read and follow instructions. A sign that humans ignore, agents obey.

## Quick Start

### Query an APS server

```bash
# Resolve a service procedure
curl -s http://aps.example.com:9090/resolve/my-api

# Resolve with scope
curl -s http://aps.example.com:9090/resolve/freeipa?scope=certs

# List all services
curl -s http://aps.example.com:9090/services

# Health check
curl -s http://aps.example.com:9090/health
```

### CLI tool

```bash
apslookup my-api
apslookup freeipa -s certs
apslookup freeipa --scopes
apslookup -l
apslookup --health
```

### DNS discovery

```
_aps._tcp.example.com. 3600 IN SRV 10 0 9090 aps.example.com.
```

## Specification

The full specification is in [APS-SPEC-001.md](APS-SPEC-001.md).

## Reference Implementation

A reference APS server implementation is included in the `aps-server/` directory:

- **Language:** Python 3.12+ (FastAPI + Uvicorn)
- **Storage:** Static JSON file (no database)
- **Security:** Per-IP rate limiting, HMAC-SHA256 config integrity, read-only container
- **Dependencies:** 5 packages, all open source
- **Container:** Docker, non-root, read-only filesystem, no capabilities

```bash
cd aps-server
docker compose up --build -d
```

## Project Structure

```
agent-procedure-service/
├── APS-SPEC-001.md          # Formal specification
├── README.md                # This file
├── aps-server/              # Reference server implementation
│   ├── aps/                 # Python package
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── apslookup           # CLI query tool
└── examples/                # Example procedure records
```

## Status

APS is in active development. The specification is a working draft. The reference implementation is functional and deployed internally.

Contributions, feedback, and discussion welcome via GitHub Issues.

## License

Apache 2.0
