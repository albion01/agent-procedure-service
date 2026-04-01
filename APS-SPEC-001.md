# APS-SPEC-001: Agent Procedure Service (APS)

**Status:** Draft
**Author:** Craig Manske
**Date:** 2026-03-26
**Revision:** 4
**Audit:** Passed internal audit 2026-03-26. Revision 4 addresses all findings.
**Category:** Standards Track — Agentic Infrastructure
**Repository:** https://github.com/[TBD]/agent-procedure-service

---

## Abstract

This document specifies the **Agent Procedure Service (APS)**, a protocol and server for publishing machine-readable instructions that tell AI agents how to interact with services. APS is to service interaction what DNS is to name resolution: a universal, standalone, **unauthenticated** lookup system that any organization can deploy and any agent can query without credentials.

All read endpoints are public. Procedures are instructions, not secrets. The security gate is at the target service, not at the directory. Authentication is required only for the management/reload endpoint that updates procedure records.

APS introduces a new category of security control — **Agentic Procedural Controls (APCs)** — designed for autonomous software agents that reliably read and follow written instructions.

---

## 1. Problem Statement

### 1.1 Agents Are the New Clients

AI agents are increasingly operating as autonomous clients — authenticating to APIs, executing commands, and interacting with services on behalf of users. Unlike human users, agents:

- Do not attend training or read onboarding documentation
- Do not have institutional memory of how a service works
- Will attempt connections using whatever method they can infer, often incorrectly
- Generate significant traffic through trial-and-error authentication

### 1.2 The Cost of Uninstructed Agents

Without a standard way to communicate procedures, both sides lose:

**Service operators** experience:
- Wasted bandwidth from malformed requests and failed authentication attempts
- Security alerts from agents brute-forcing endpoints
- Rate limiting that penalizes legitimate agent users alongside bad actors
- Support burden from agent operators asking "how do I connect?"

**Agent operators** experience:
- Failed connections and wasted compute cycles
- Credential leakage when agents guess at authentication methods
- Inconsistent behavior across services with no standard interface
- Agents taking dangerous shortcuts (reading config files, hardcoding credentials)

### 1.3 No Existing Standard

Current approaches to this problem are all inadequate:

| Approach | Problem |
|----------|---------|
| Documentation (README, API docs) | Designed for humans, not machine-readable |
| `robots.txt` | Tells agents what NOT to do, not HOW to do things correctly |
| OpenAPI/Swagger | Describes API shape, not authentication procedures or restrictions |
| `.well-known` URIs | Requires the service itself to be reachable (chicken-and-egg) |
| Agent configuration files | Scattered, stale, not authoritative |
| MCP (Model Context Protocol) | Defines how agents connect to tools, not how to discover and authenticate to services |
| A2A (Agent-to-Agent Protocol) | Defines agent-to-agent communication, not agent-to-service procedure resolution |
| OpenID Connect Discovery (`.well-known/openid-configuration`) | Machine-readable auth endpoint discovery, but lives on the service itself (unavailable when service is down) |

**Complementary protocols:**

- **MCP (Model Context Protocol)** — Defines how agents connect to tools. APS is complementary: APS tells agents how to connect to services; MCP defines what agents can do once connected.
- **A2A (Agent-to-Agent Protocol)** — Defines agent-to-agent communication. APS is agent-to-service procedure resolution. They operate at different layers.
- **OpenID Connect Discovery (`.well-known/openid-configuration`)** — Machine-readable auth endpoint discovery. Similar concept but lives on the service itself (unavailable when service is down). APS is independent of the services it describes.

APS fills this gap: a **service-independent, machine-readable, universally queryable** system for publishing interaction procedures.

---

## 2. Design Principles

### 2.1 The Fire Extinguisher Principle

A fire extinguisher has its operating procedure printed directly on it. Nobody memorizes the procedure — you read it when you need it. APS applies this principle: the procedure for interacting with a service is published at a known location and read at the time of interaction.

### 2.2 The DNS Analogy

DNS is a universal resolver: every networked application calls `gethostbyname()` before connecting. APS provides a universal resolver for procedures: every agent calls `getprocedure()` before interacting. The parallels are deliberate:

| DNS | APS |
|-----|-----|
| Resolves names to addresses | Resolves services to procedures |
| Authoritative nameservers | Authoritative APS servers |
| Zone files | Procedure records |
| `A` records (addresses) | `PROC` records (procedures) |
| Recursive resolvers / caching | Agent-side caching |
| `dig` CLI tool | `aps-resolve` CLI tool |
| Runs independently of the services it describes | Runs independently of the services it describes |
| Free to query, no authentication | Free to query, no authentication |

### 2.3 Independence

APS MUST NOT depend on any other service to function. It is a standalone server with its own storage, its own protocol, and its own deployment. If the services it describes go down, APS continues serving their procedures. If other infrastructure fails (databases, identity providers, monitoring), APS continues serving.

### 2.4 Free to Query, No Authentication

APS read endpoints are public. No API keys, no tokens, no agent identity verification. The rationale:

- Procedures are instructions, not secrets. They describe *how* to authenticate to a service, not *what* the credentials are.
- Requiring auth to learn how to auth creates a bootstrapping problem.
- DNS is free to query. APS is too.
- Public procedures incentivize correct agent behavior, reducing abuse.
- Making procedures available to all agents — including unknown or new ones — is a feature, not a risk.

Rate limiting protects against abuse (see Section 5).

### 2.5 Least Functionality

APS procedure records define the agent's operational universe for a given service. Every record begins with a boundary: the agent SHOULD only perform operations documented in the procedure record. This constrains the agent to the intended scope without requiring technical enforcement at the APS layer — the enforcement happens at the target service through its own access controls.

This principle aligns with NIST SP 800-171r3 control 03.04.06 (Least Functionality): configure systems to provide only essential capabilities and prohibit unauthorized functions. APS extends this concept to agentic operations by declaring the authorized operations upfront.

### 2.6 Open Standards Only

APS uses only free, open standards:

| Component | Standard |
|-----------|----------|
| Data format | JSON (RFC 8259) |
| Transport | HTTP/1.1+ (RFC 9110-9114) |
| Integrity | HMAC-SHA256 (RFC 2104) |
| Hashing | SHA-256 (FIPS 180-4) |
| Character encoding | UTF-8 (RFC 3629) |
| Timestamps | RFC 3339 (a profile of ISO 8601) |
| TLS (optional) | TLS 1.2+ (RFC 5246, 8446) |

No proprietary formats, no vendor-locked dependencies, no patent-encumbered algorithms.

---

## 3. Protocol Specification

### 3.1 Record Types

APS defines one primary record type: the **Procedure Record**.

```json
{
  "v": "aps1",
  "service": "api.example.com",
  "scope": null,
  "name": "Example API",
  "url": "https://api.example.com",
  "type": "api",
  "auth": {
    "method": "bearer-token",
    "token_source": "Contact admin@example.com for API key",
    "token_header": "Authorization",
    "token_prefix": "Bearer"
  },
  "procedure": [
    "ONLY perform operations documented in this APS record.",
    "Obtain an API key from https://example.com/developer/keys",
    "Include the key in the Authorization header: Bearer {key}",
    "Base URL: https://api.example.com/v2/",
    "Rate limit: 100 requests per minute",
    "API documentation: https://docs.example.com"
  ],
  "restrictions": [
    "Do not exceed 100 requests per minute",
    "Do not scrape bulk data without prior arrangement",
    "Do not store or redistribute user data"
  ],
  "contact": "admin@example.com",
  "updated": "2026-03-26T12:00:00Z"
}
```

### 3.2 Record Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `v` | string | Yes | Protocol version. MUST be `"aps1"` for this specification. |
| `service` | string | Yes | Service identifier. SHOULD match the service's primary hostname. Multiple records MAY share the same `service` value if they have different `scope` values. |
| `scope` | string | No | Operation category within a service (e.g., `"certs"`, `"users"`, `"dns"`). When null or omitted, the record is the default/general procedure for the service. See Section 3.7. |
| `name` | string | Yes | Human-readable service name. |
| `url` | string | Yes | Service base URL or connection string. |
| `type` | string | Yes | Service type: `"api"`, `"ssh"`, `"web"`, `"database"`, `"smtp"`, or custom. Agents SHOULD attempt to follow the procedure regardless of unrecognized `type` values. |
| `auth` | object | No | How to authenticate to the TARGET SERVICE (see 3.3). This describes authentication at the service, not at APS. Omit if no auth required. |
| `procedure` | array[string] | Yes | Ordered steps the agent MUST follow. Plain language, imperative mood. The first step SHOULD be a Least Functionality boundary statement. |
| `restrictions` | array[string] | No | Actions the agent MUST NOT take. |
| `rate_limit` | object | No | Rate limit information: `{"requests": 100, "period": "minute"}`. Valid `period` values: `"second"`, `"minute"`, `"hour"`, `"day"`. |
| `contact` | string | No | Contact for questions or key requests. |
| `tags` | array[string] | No | Categorization tags. |
| `ttl` | integer | No | Cache duration in seconds. Default: 3600 (1 hour). |
| `updated` | string | No | RFC 3339 timestamp of last update. |

### 3.3 Authentication Object

The `auth` field describes how an agent authenticates **to the target service** — not to APS itself. APS has no authentication on read endpoints. The `auth` object tells the agent the method and where to obtain credentials, but does NOT contain credentials.

| Field | Type | Description |
|-------|------|-------------|
| `method` | string | Auth method at the target service: `"bearer-token"`, `"api-key"`, `"basic"`, `"oauth2"`, `"ssh-key"`, `"kerberos"`, `"session-cookie"`, `"client-cert"`, `"none"` |
| `token_source` | string | How to obtain credentials (human-readable instruction) |
| `token_header` | string | HTTP header name for the token (e.g., `"Authorization"`, `"X-API-Key"`) |
| `token_prefix` | string | Prefix before the token value (e.g., `"Bearer"`, `"Token"`) |
| `oauth2_token_url` | string | OAuth2 token endpoint (for `method: "oauth2"`) |
| `oauth2_scopes` | array[string] | Required OAuth2 scopes |
| `ssh_user` | string | SSH username (for `method: "ssh-key"`) |
| `details` | object | Additional auth-specific configuration |

APS tells the agent HOW to authenticate, not WHERE the credentials are stored. For example, a record might say "authenticate via Kerberos using your service principal" but would never include the keytab or password. The agent must already have access to the credential store referenced by `token_source`.

### 3.4 Server Endpoints

An APS server MUST implement the following endpoints. **All read endpoints (resolve, services, health, metrics) require NO authentication.** Only the management reload endpoint requires authentication.

#### 3.4.1 Resolve (Required, Public)

```
GET /resolve/{service}
GET /resolve/{service}?scope={scope}
```

Returns the Procedure Record(s) for the named service. Case-insensitive lookup.

When called without `scope`, returns all records for the service (the default/unscoped record plus all scoped records). When called with `scope`, returns only the record matching that scope.

The response MUST always use the `records` array wrapper regardless of count. Clients MUST NOT assume the shape varies by scope.

**Response 200 (no scope filter — returns all records):**
```json
{
  "records": [
    { "v": "aps1", "service": "freeipa.example.com", "scope": "certs", ... },
    { "v": "aps1", "service": "freeipa.example.com", "scope": "users", ... },
    { "v": "aps1", "service": "freeipa.example.com", "scope": "dns", ... }
  ],
  "count": 3
}
```

**Response 200 (with scope filter — returns single matching record):**
```json
{
  "records": [
    { "v": "aps1", "service": "freeipa.example.com", "scope": "certs", ... }
  ],
  "count": 1
}
```

**Response 200 (single unscoped record):**
```json
{
  "records": [
    { "v": "aps1", "service": "api.example.com", "scope": null, ... }
  ],
  "count": 1
}
```

**Response 404:**
```json
{"error": "not_found", "message": "No procedure registered for 'unknown-service'"}
```

#### 3.4.2 List Services (Required, Public)

```
GET /services
```

Returns all registered service names with their available scopes.

**Response 200:**
```json
{
  "services": [
    {"service": "api.example.com", "scopes": [null]},
    {"service": "freeipa.example.com", "scopes": ["certs", "users", "dns"]},
    {"service": "ssh.example.com", "scopes": [null]}
  ],
  "count": 3
}
```

Supports optional query parameters `?tag=<tag>` and `?scope=<scope>` for filtering.

#### 3.4.3 Health (Required, Public)

```
GET /health
```

**Response 200:**
```json
{
  "status": "ok",
  "version": "aps1",
  "procedures_count": 42,
  "uptime_seconds": 86400,
  "config_updated": "2026-03-26T12:00:00Z"
}
```

#### 3.4.4 Metrics (Optional, Public)

```
GET /metrics
```

Prometheus-compatible metrics. See Section 6.

> **WARNING:** Metrics may expose internal service inventory and query patterns. Operators SHOULD evaluate whether public metrics exposure is acceptable. Consider restricting `/metrics` to trusted IPs or requiring authentication in sensitive environments.

#### 3.4.5 Error Response Schema

All non-200 responses MUST use this error envelope:

```json
{"error": "not_found", "message": "Human-readable description"}
```

Defined error codes:

| Code | HTTP Status | Description |
|------|------------|-------------|
| `not_found` | 404 | No procedure registered for the requested service/scope |
| `rate_limited` | 429 | Client has exceeded the rate limit |
| `banned` | 403 | Client IP is temporarily banned due to repeated rate limit violations |
| `unauthorized` | 401 | Missing or invalid management key on authenticated endpoint |
| `invalid_config` | 400 | Config envelope failed validation (malformed records) |
| `replay_rejected` | 409 | Config version is less than or equal to the currently installed version |
| `integrity_failed` | 400 | HMAC signature verification failed |
| `server_error` | 500 | Internal server error |

#### 3.4.6 Input Validation

The `service` path parameter MUST be validated: alphanumeric characters, hyphens, and dots only. Path traversal sequences (`../`, `%2F`) MUST be rejected. Maximum length: 253 characters (matching DNS label limits).

#### 3.4.7 Reload (Required, Authenticated)

```
POST /config/reload
X-Management-Key: {management_key}
Content-Type: application/json

{config envelope}
```

This is the **only authenticated endpoint** on an APS server. It accepts a signed configuration envelope and atomically updates the procedure records. See Section 3.6.3.

### 3.5 DNS Discovery

APS servers SHOULD be discoverable via DNS SRV records:

```
_aps._tcp.example.com. 3600 IN SRV 10 0 9090 aps.example.com.
```

This allows agents to discover the APS server for any domain, similar to how `_dmarc`, `_mta-sts`, and other policy records are published. Agents MUST follow the priority and weight selection algorithm defined in RFC 2782 when multiple SRV records are present.

Agents SHOULD attempt to discover APS by querying `_aps._tcp.<domain>` where `<domain>` is the registrable domain of the target service URL.

Additionally, a minimal APS TXT record MAY be published on the service hostname itself as a fast-path hint:

```
api.example.com. IN TXT "v=aps1 aps=http://aps.example.com:9090/resolve/api.example.com"
```

This tells agents: "there is an APS record for this service — query the referenced URL for the full procedure." Agents that see this TXT record during normal DNS resolution can proactively fetch the procedure.

### 3.6 Config Management

APS servers serve from a static configuration file. The configuration is managed externally and pushed to the APS server. This keeps the server simple and read-only at runtime.

#### 3.6.1 Configuration Envelope

```json
{
  "aps_version": "aps1",
  "config_version": 3,
  "generated_at": "2026-03-26T12:00:00Z",
  "source": "admin.example.com",
  "hmac_signature": "a1b2c3d4e5f6...",
  "procedures": [
    { "v": "aps1", "service": "api.example.com", "scope": null, ... },
    { "v": "aps1", "service": "freeipa.example.com", "scope": "certs", ... },
    { "v": "aps1", "service": "freeipa.example.com", "scope": "users", ... },
    { "v": "aps1", "service": "ssh.example.com", "scope": null, ... }
  ]
}
```

The envelope contains no API keys or agent credentials — only the management key protects the reload endpoint, and it is passed in the HTTP header, not stored in the envelope.

#### 3.6.2 Integrity Verification

The `hmac_signature` field contains an HMAC-SHA256 digest computed over the entire config envelope (excluding the `hmac_signature` field itself), serialized as canonical JSON (sorted keys, no whitespace). The shared secret is established between the configuration management system and the APS server.

The signing input is the raw UTF-8 bytes of the canonical JSON serialization. Implementations MUST NOT perform Unicode normalization before signing.

APS servers MUST verify the HMAC signature before accepting new configuration. If verification fails, the server MUST reject the update and continue serving the previous configuration.

#### 3.6.3 Reload Endpoint

The reload endpoint is the only write operation and the only authenticated endpoint on an APS server. It is authenticated with a management key (separate from any agent or service credentials). The server:

1. Verifies the management key
2. Rejects any config envelope with a `config_version` less than or equal to the currently installed version (replay protection)
3. Verifies the HMAC signature
4. Validates all procedure records
5. Atomically swaps the in-memory data
6. Writes the new configuration to disk

Servers MUST reject any config envelope with a `config_version` less than or equal to the currently installed version. This prevents replay attacks using captured valid requests.

### 3.7 Scoped Records

A single service often exposes multiple distinct operation domains. For example, FreeIPA provides certificate services, user management, DNS, and HBAC configuration — each with different procedures, different API methods, and different restrictions. Rather than creating artificial service names like `freeipa-certs` and `freeipa-dns`, APS supports **scoped records**: multiple procedure records sharing the same `service` identifier, differentiated by `scope`.

#### 3.7.1 Design Rationale

Scoping is about **relevance, not access control**. Anyone can read any procedure record regardless of scope. The scope is a convenience filter that lets an agent request only the procedures relevant to its current task. An agent performing certificate operations queries `?scope=certs` and receives only the certificate procedure — not the DNS or user management procedures it does not need.

#### 3.7.2 Example: FreeIPA Scoped Records

```json
[
  {
    "v": "aps1",
    "service": "freeipa.cmdottie.local",
    "scope": "certs",
    "name": "FreeIPA Certificate Services",
    "url": "https://freeipa.cmdottie.local/ipa",
    "type": "api",
    "auth": {
      "method": "kerberos",
      "token_source": "Authenticate via kinit using your service principal or AppRole credentials from Vault",
      "details": {
        "realm": "CMDOTTIE.LOCAL",
        "required_header": "Referer: https://freeipa.cmdottie.local/ipa"
      }
    },
    "procedure": [
      "ONLY perform certificate operations documented in this APS record.",
      "Authenticate to FreeIPA using Kerberos (kinit with your service principal).",
      "All API calls require the header: Referer: https://freeipa.cmdottie.local/ipa",
      "To request a certificate: submit a CSR via the cert_request JSON-RPC method.",
      "Do NOT generate CA certificates, sign certificates locally, or create local CAs.",
      "FreeIPA is the ONLY authorized CA in this environment.",
      "Record every certificate event as a change record: CN, SANs, serial, validity, deployment location."
    ],
    "restrictions": [
      "Do not issue certificates without explicit user instruction.",
      "Do not use openssl ca, openssl x509 -signkey, or any local signing method.",
      "Do not revoke certificates without explicit user instruction."
    ],
    "contact": "admin@cmdottie.local",
    "updated": "2026-03-26T12:00:00Z"
  },
  {
    "v": "aps1",
    "service": "freeipa.cmdottie.local",
    "scope": "users",
    "name": "FreeIPA User Management",
    "url": "https://freeipa.cmdottie.local/ipa",
    "type": "api",
    "auth": {
      "method": "kerberos",
      "token_source": "Authenticate via kinit using your service principal",
      "details": {
        "realm": "CMDOTTIE.LOCAL",
        "required_header": "Referer: https://freeipa.cmdottie.local/ipa"
      }
    },
    "procedure": [
      "ONLY perform user management operations documented in this APS record.",
      "Authenticate to FreeIPA using Kerberos.",
      "All API calls require the header: Referer: https://freeipa.cmdottie.local/ipa",
      "Use user_find to search, user_show to inspect, user_add to create.",
      "All new accounts MUST use FreeIPA as the identity source.",
      "Record every account change as a change record."
    ],
    "restrictions": [
      "Do not delete user accounts without explicit user instruction.",
      "Do not modify admin or root accounts.",
      "Do not disable accounts without explicit user instruction."
    ],
    "contact": "admin@cmdottie.local",
    "updated": "2026-03-26T12:00:00Z"
  },
  {
    "v": "aps1",
    "service": "freeipa.cmdottie.local",
    "scope": "dns",
    "name": "FreeIPA DNS Management",
    "url": "https://freeipa.cmdottie.local/ipa",
    "type": "api",
    "auth": {
      "method": "kerberos",
      "token_source": "Authenticate via kinit with a principal that has DNS Administrators privilege",
      "details": {
        "realm": "CMDOTTIE.LOCAL",
        "required_header": "Referer: https://freeipa.cmdottie.local/ipa"
      }
    },
    "procedure": [
      "ONLY perform DNS operations documented in this APS record.",
      "Authenticate to FreeIPA using Kerberos with DNS Administrators privilege.",
      "All API calls require the header: Referer: https://freeipa.cmdottie.local/ipa",
      "Use dnsrecord_find to list, dnsrecord_show to inspect, dnsrecord_add to create.",
      "Supported record types: A, AAAA, CNAME, SRV, TXT, PTR.",
      "Record every DNS change as a change record."
    ],
    "restrictions": [
      "Do not delete DNS zones.",
      "Do not modify SOA records.",
      "Do not create wildcard records without explicit user instruction."
    ],
    "contact": "admin@cmdottie.local",
    "updated": "2026-03-26T12:00:00Z"
  }
]
```

**Agent query examples:**
- `GET /resolve/freeipa.cmdottie.local` — returns all three scoped records
- `GET /resolve/freeipa.cmdottie.local?scope=certs` — returns only the certificate procedure
- `GET /resolve/freeipa.cmdottie.local?scope=dns` — returns only the DNS procedure

#### 3.7.3 Scope Naming Conventions

Scopes SHOULD be short, lowercase, hyphen-separated identifiers that describe the operation domain:

| Good | Bad |
|------|-----|
| `certs` | `certificate-management-operations` |
| `users` | `UserAdmin` |
| `dns` | `DNS_Records` |
| `hbac` | `host-based-access-control-rules` |

Scopes are free-form strings — APS does not enforce a controlled vocabulary. Organizations SHOULD document their scope naming conventions.

---

## 4. Agentic Procedural Controls (APCs)

### 4.1 A New Control Category

Traditional security controls address human actors:

| Control Type | Target | Mechanism |
|-------------|--------|-----------|
| Technical | Systems | Enforcement (firewalls, ACLs) |
| Administrative | Humans | Policy and training |
| Physical | Humans | Barriers and deterrence (locks, signs) |

AI agents are a new class of actor. They are not systems (they have judgment and flexibility), not humans (they don't internalize training), and not physically present. None of the traditional control categories adequately address them.

APS introduces **Agentic Procedural Controls (APCs)** — a fourth control category:

| Control Type | Target | Mechanism |
|-------------|--------|-----------|
| **Agentic Procedural** | **AI Agents** | **Machine-readable instructions at the point of action** |

### 4.2 Why APCs Work

APCs exploit a unique property of AI agents: **they reliably read and follow written instructions.** A sign on a door that says "Authorized Personnel Only" works poorly for humans (they ignore signs). The same sign works well for agents (they read it, process it, and comply).

Properties of effective APCs:
1. **Point-of-use delivery** — instructions encountered when the agent needs them
2. **Machine-readable format** — structured data that agents parse reliably
3. **Authoritative source** — one canonical location, centrally managed
4. **Self-describing** — includes why, what, and how
5. **Universally accessible** — free to query, no bootstrapping problem

### 4.3 APCs vs robots.txt

`robots.txt` is the closest existing analog to an APC. Both are machine-readable instructions published by service operators for autonomous software agents. The differences:

| Property | robots.txt | APS |
|----------|-----------|-----|
| Tells agents | What NOT to crawl | How to interact correctly |
| Data format | Custom line-based format | JSON |
| Location | On the service itself (`/robots.txt`) | Separate APS server |
| Scope | Web crawling only | Any service interaction |
| Availability | Requires the service to be reachable | Independent of the service |

APS and robots.txt are complementary. robots.txt restricts crawling. APS instructs interaction.

### 4.4 Least Functionality in APCs

Every APS procedure record SHOULD begin with a **Least Functionality boundary**: a statement that restricts the agent to only the operations documented in that record. This is the first line of the `procedure` array:

```json
"procedure": [
  "ONLY perform operations documented in this APS record.",
  "..."
]
```

This boundary serves multiple purposes:
- **Defines the operational universe.** The agent knows exactly what it is authorized to do.
- **Prevents scope creep.** An agent querying the DNS procedure does not attempt certificate operations, even if it knows how.
- **Creates an audit trail.** If an agent performs an undocumented operation, the APS record proves the action was outside its procedural scope.
- **Complements technical controls.** The target service enforces access via its own ACLs and permissions. The APS boundary prevents the agent from even attempting unauthorized operations, reducing noise and failed requests.

Least Functionality boundaries are advisory — they rely on the agent's instruction-following behavior, not technical enforcement. This is by design: APCs are a control category for agents that read and follow instructions. Agents that ignore APS records are no different from humans who ignore policy — the technical controls at the service layer remain the enforcement backstop.

### 4.5 APCs Beyond Authentication

While this specification focuses on service connection procedures, the APC concept extends to any domain where agents need instructions:

- **Data handling:** "This API returns PII — do not log response bodies"
- **Change management:** "Create a change record before modifying resources"
- **Compliance:** "This service processes healthcare data — HIPAA restrictions apply"
- **Rate management:** "Batch requests during off-peak hours (00:00-06:00 UTC)"
- **Escalation:** "If this service returns 503, do not retry — contact ops@example.com"

---

## 5. Security Considerations

### 5.1 DDoS Protection

APS servers are publicly accessible and must be resilient to denial-of-service attacks.

#### 5.1.1 Rate Limiting

APS servers MUST implement rate limiting:

| Limit | Default | Description |
|-------|---------|-------------|
| Per-IP | 30 requests/minute | Prevents single-source flooding |
| Global | 300 requests/minute | Prevents distributed flooding |
| Ban threshold | 5 violations | Temp-bans repeat offenders |
| Ban duration | 5 minutes | Automatic expiry |

Rate limit responses use HTTP 429 with a `Retry-After` header.

Ban events MUST be logged with the client IP (or hash) and timestamp.

#### 5.1.2 Request Guards

- Maximum request body size: 1 MB (only applicable to POST /config/reload)
- Connection timeout: 10 seconds
- Keep-alive timeout: 5 seconds (mitigates slowloris attacks)
- Maximum concurrent connections: 50

#### 5.1.3 Minimal Attack Surface

APS servers expose no write operations except the authenticated config reload endpoint. There is no database, no ORM, no SQL, no file upload, no user input that reaches a shell. The attack surface is deliberately minimal.

### 5.2 Procedures Are Public by Design

APS procedure records are public. This is intentional, not an oversight. Procedures describe *how* to authenticate to a service, not *what* the credentials are. Publishing procedures openly:

- **Eliminates the bootstrapping problem.** An agent does not need credentials to learn how to obtain credentials.
- **Reduces attack surface.** No authentication system means no authentication vulnerabilities on read endpoints.
- **Follows the DNS model.** DNS records are public. Anyone can query `dig A example.com`. APS follows the same principle — anyone can query `GET /resolve/example.com`.
- **Incentivizes correct behavior.** Agents that can freely discover procedures are less likely to brute-force, guess, or take dangerous shortcuts.

Organizations MUST NOT publish credentials, tokens, passwords, or private keys in APS records.

**Acceptable:** `"token_source": "Authenticate to Vault using your AppRole credentials"`
**NOT acceptable:** `"token": "sk-abc123secret"`

If an organization has procedures that genuinely contain secrets (e.g., internal network topology details they wish to protect), those details should be kept in the credential store referenced by the procedure, not in the procedure itself.

### 5.3 Integrity Protection

Configuration pushed to APS servers is signed with HMAC-SHA256 (RFC 2104). This ensures:

- Configuration cannot be tampered with in transit
- Only holders of the shared secret can update procedures
- The APS server can verify the configuration source

If an APS server cannot verify the signature of a new configuration, it MUST reject the update and continue serving the previous known-good configuration.

### 5.4 Management Endpoint Protection

The `/config/reload` endpoint is the only write path and the only authenticated endpoint. It MUST be protected:

- Authenticated with a management key via `X-Management-Key` header
- The management key SHOULD be long (256+ bits of entropy) and rotated periodically
- The management key SHOULD be stored in a secrets manager (e.g., HashiCorp Vault). It MUST NOT be stored in the config file, source code, or environment that is accessible to non-administrative users.
- The endpoint SHOULD be restricted by source IP where possible (e.g., only the configuration management host)
- Failed authentication attempts MUST be logged
- TLS is REQUIRED for any deployment where the reload endpoint is reachable over an untrusted network. The management key is transmitted in an HTTP header and MUST be protected by transport encryption.

### 5.5 Server Hardening

APS server deployments SHOULD:

- Run as a non-root, unprivileged user
- Use a read-only filesystem (except the config data directory)
- Drop all OS capabilities
- Disable privilege escalation
- Limit memory and CPU allocation
- Disable all unnecessary features (API documentation UIs, debug endpoints)
- Log structured events without sensitive data

### 5.6 Malicious Procedure Records

If the management key or HMAC secret is compromised, an attacker can push malicious procedures redirecting agents to attacker-controlled services — the APS equivalent of DNS poisoning. Mitigations:

- Rotate management keys and HMAC secrets on any suspected compromise
- Re-verify all procedure records after a compromise
- Agents SHOULD validate that `url` fields in procedure records are consistent with the expected service domain
- Monitor for unexpected changes in procedure count or content via the health endpoint

---

## 6. Implementation Guidelines

### 6.1 Server Requirements

A conforming APS server:

- MUST serve JSON responses with `Content-Type: application/json`
- MUST implement `/resolve/{service}`, `/services`, `/health`, and `/config/reload` endpoints
- MAY implement `/metrics` (OPTIONAL)
- MUST serve `/resolve`, `/services`, and `/health` without authentication
- If `/metrics` is implemented, it MUST be served without authentication by default (but operators MAY restrict access)
- MUST require authentication on `/config/reload`
- MUST perform case-insensitive service name lookups
- MUST support the `scope` query parameter on `/resolve/{service}`
- MUST verify HMAC signatures on configuration updates
- MUST implement per-IP rate limiting
- MUST respond to `/health` within 100ms
- MUST respond to `/resolve/{service}` within 50ms (excluding network latency)
- SHOULD run on port 9090 by default
- SHOULD support TLS termination

### 6.2 Agent Requirements

A conforming APS client (agent):

- MUST query APS before interacting with any service for the first time, if an APS server is known
- SHOULD include `scope` when querying for a specific operation domain
- MUST follow the `procedure` steps in order
- MUST obey all `restrictions`
- MUST obey the Least Functionality boundary (first procedure step)
- SHOULD cache procedure records for the duration specified by `ttl`
- If APS is unreachable, agents SHOULD use cached procedures if available (respecting TTL). If no cached procedure exists, agents MUST NOT guess at connection procedures — they SHOULD report the APS failure to the user and await instructions.
- MUST NOT reject records with unrecognized `v` values if they can still parse the required fields. Unknown fields in procedure records MUST be ignored, not rejected.

### 6.3 DNS Integration

Organizations SHOULD publish an SRV record for APS discovery:

```
_aps._tcp.example.com. 3600 IN SRV 10 0 9090 aps.example.com.
```

Organizations MAY publish TXT hint records on service hostnames:

```
api.example.com. IN TXT "v=aps1 aps=http://aps.example.com:9090/resolve/api.example.com"
```

Agents SHOULD check for SRV records when no APS server is explicitly configured.

### 6.4 Caching

Agents SHOULD cache resolved procedures to reduce APS server load. The `ttl` field specifies cache duration in seconds. If not present, agents SHOULD use a default TTL of 3600 seconds (1 hour).

Agents MUST respect the TTL — do not cache indefinitely, as procedures change.

### 6.5 Reference Implementation

A reference implementation of an APS server is available at:
- Repository: `https://github.com/[TBD]/aps-server`
- Language: Python 3.12+ (FastAPI + Uvicorn)
- License: Apache 2.0
- Dependencies: 5 (fastapi, uvicorn, pydantic, pydantic-settings, prometheus-client)

---

## 7. Examples

### 7.1 Public REST API

```json
{
  "v": "aps1",
  "service": "api.weather.gov",
  "scope": null,
  "name": "National Weather Service API",
  "url": "https://api.weather.gov",
  "type": "api",
  "auth": {
    "method": "none"
  },
  "procedure": [
    "ONLY perform operations documented in this APS record.",
    "No authentication required.",
    "Set a descriptive User-Agent header: (your-app, contact-email)",
    "Base URL: https://api.weather.gov",
    "Documentation: https://www.weather.gov/documentation/services-web-api"
  ],
  "restrictions": [
    "Do not exceed reasonable request rates",
    "Include a User-Agent header identifying your application"
  ],
  "rate_limit": {"requests": 60, "period": "minute"},
  "contact": "nws.api@noaa.gov"
}
```

### 7.2 SSH Server

```json
{
  "v": "aps1",
  "service": "bastion.example.com",
  "scope": null,
  "name": "Production Bastion Host",
  "url": "ssh://bastion.example.com:22",
  "type": "ssh",
  "auth": {
    "method": "ssh-key",
    "ssh_user": "deploy",
    "token_source": "Submit SSH public key to infra-team@example.com"
  },
  "procedure": [
    "ONLY perform operations documented in this APS record.",
    "Connect using your authorized SSH key: ssh deploy@bastion.example.com",
    "Do not use password authentication — it is disabled",
    "Port forwarding is allowed for approved services only",
    "Session timeout: 30 minutes of inactivity"
  ],
  "restrictions": [
    "Do not install software on the bastion host",
    "Do not modify system configuration",
    "Do not use the bastion for outbound internet access"
  ],
  "contact": "infra-team@example.com"
}
```

### 7.3 Internal Service with Vault-Based Auth

```json
{
  "v": "aps1",
  "service": "netbox.internal",
  "scope": null,
  "name": "NetBox DCIM/IPAM",
  "url": "http://netbox.internal:8000",
  "type": "api",
  "auth": {
    "method": "api-key",
    "token_header": "Authorization",
    "token_prefix": "Token",
    "token_source": "Authenticate to Vault using your AppRole, then read secret/data/services/netbox field=api_token",
    "details": {
      "vault_path": "secret/data/services/netbox",
      "vault_field": "api_token"
    }
  },
  "procedure": [
    "ONLY perform operations documented in this APS record.",
    "Authenticate to Vault using your AppRole credentials.",
    "Read the API token from Vault path: secret/data/services/netbox",
    "Include header: Authorization: Token {api_token}",
    "API base: http://netbox.internal:8000/api/"
  ],
  "restrictions": [
    "Read-only access unless explicitly authorized for write operations",
    "Do not delete devices, sites, or IP address records",
    "Create a change record for any modifications"
  ]
}
```

### 7.4 OAuth2 Service

```json
{
  "v": "aps1",
  "service": "api.github.com",
  "scope": null,
  "name": "GitHub REST API",
  "url": "https://api.github.com",
  "type": "api",
  "auth": {
    "method": "oauth2",
    "oauth2_token_url": "https://github.com/login/oauth/access_token",
    "oauth2_scopes": ["repo", "read:org"],
    "token_header": "Authorization",
    "token_prefix": "Bearer",
    "token_source": "Create a personal access token at https://github.com/settings/tokens"
  },
  "procedure": [
    "ONLY perform operations documented in this APS record.",
    "Obtain a token via OAuth2 or personal access token.",
    "Include header: Authorization: Bearer {token}",
    "API base: https://api.github.com",
    "Use Accept: application/vnd.github+json header",
    "Include X-GitHub-Api-Version: 2022-11-28 header"
  ],
  "restrictions": [
    "Respect rate limits: 5000 requests/hour for authenticated requests",
    "Do not create repositories or modify organization settings without explicit authorization"
  ],
  "rate_limit": {"requests": 5000, "period": "hour"}
}
```

---

## 8. Future Work

- **APS-over-DNS:** Define a compact TXT record format for lightweight procedure hints, with pointers to full APS records for complex procedures.
- **Signed records:** Individual procedure records signed with public key cryptography (Ed25519), allowing verification without a shared secret.
- **Federation:** APS servers forwarding queries for unknown services to upstream APS servers, like DNS recursion.
- **Agent identity:** Standard for agents to identify themselves to APS (User-Agent equivalent for agents). Note: this is for analytics and debugging, not access control — reads remain public.
- **Procedure versioning:** Multiple versions of a procedure for the same service (e.g., v1 API vs v2 API).
- **IANA registration:** Register `_aps._tcp` as a service type and port 9090 as the default APS port.
- **Scope registry:** Optional well-known scope names for common operation domains (certs, users, dns, etc.).

---

## 9. References

- RFC 2104 — HMAC: Keyed-Hashing for Message Authentication
- RFC 2782 — DNS SRV Records
- RFC 3339 — Date and Time on the Internet: Timestamps (a profile of ISO 8601)
- RFC 3629 — UTF-8
- RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format
- RFC 8615 — Well-Known URIs
- RFC 9110-9114 — HTTP Semantics and HTTP/1.1, HTTP/2, HTTP/3
- FIPS 180-4 — Secure Hash Standard (SHA-256)
- NIST SP 800-171r3 — Protecting Controlled Unclassified Information in Nonfederal Systems and Organizations (control 03.04.06, Least Functionality)

---

## Appendix A: Terminology

| Term | Definition |
|------|-----------|
| **APS** | Agent Procedure Service — a standalone server that publishes machine-readable service interaction procedures. All read endpoints are public. |
| **APC** | Agentic Procedural Control — a machine-readable instruction designed for AI agents, delivered at the point of action |
| **Procedure Record** | A JSON document describing how to interact with a specific service (or a specific scope within a service) |
| **Scope** | An operation category within a service (e.g., "certs", "users", "dns") that allows multiple procedure records per service |
| **Resolve** | The act of querying APS for a service's procedure record(s) |
| **Config Envelope** | A signed JSON document containing all procedure records for an APS server |
| **Management Key** | A secret key authorizing configuration updates to an APS server (the only secret in the system) |
| **Least Functionality Boundary** | The first procedure step that restricts the agent to only operations documented in the record |

## Appendix B: Quick Reference

**Agent workflow:**
```
1. Agent needs to interact with freeipa.example.com (certificate operations)
2. Agent queries: GET http://aps.example.com:9090/resolve/freeipa.example.com?scope=certs
3. APS returns the scoped procedure record (no auth required)
4. Agent reads the Least Functionality boundary: "ONLY perform certificate operations..."
5. Agent follows the procedure steps (authenticates to FreeIPA, submits CSR, etc.)
6. Agent obeys the restrictions
7. Agent caches the record for TTL duration
```

**DNS discovery:**
```
dig SRV _aps._tcp.example.com
→ aps.example.com:9090

dig TXT api.example.com
→ "v=aps1 aps=http://aps.example.com:9090/resolve/api.example.com"
```

**Server setup:**
```
1. Deploy APS server on port 9090 (all read endpoints are public)
2. Create procedure records for your services (with scopes where needed)
3. Push configuration with HMAC-signed envelope (management key required)
4. Publish DNS SRV record: _aps._tcp.example.com → aps.example.com:9090
5. Optionally publish TXT hints on service hostnames
```

**Authentication summary:**
```
GET  /resolve/{service}     — PUBLIC, no auth
GET  /services              — PUBLIC, no auth
GET  /health                — PUBLIC, no auth
GET  /metrics               — PUBLIC, no auth
POST /config/reload         — AUTHENTICATED, requires X-Management-Key
```
