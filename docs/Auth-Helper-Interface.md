# Auth Helper Interface Specification

Nagstamon supports external auth helpers, standalone commands that handle
authentication independently of Nagstamon internals. This includes OIDC/OAuth2,
SAML, session cookies, API tokens, or any other scheme. This document defines
the CLI contract so anyone can build a compatible helper.

An example implementation is included in
[docs/example-auth-helper/nagstamon-auth-helper](example-auth-helper/nagstamon-auth-helper),
implementing OIDC Authorization Code + PKCE via the system browser.

## Overview

The helper is a command-line tool that Nagstamon invokes via subprocess. It must support
two subcommands: `get-headers` (non-interactive) and `authenticate` (interactive,
e.g. opens a browser).

Nagstamon calls `get-headers` before each polling cycle. If that fails with exit code 1,
Nagstamon automatically calls `authenticate` to trigger interactive login, then retries
`get-headers`.

## Compatible Server Types

The auth helper works by injecting HTTP headers and/or cookies into Nagstamon's
shared HTTP session. This is compatible with any server type that uses
`fetch_url()` for its HTTP communication. Server types that use their own
transport or API-level authentication will not benefit from the injected
credentials, unless an authenticating reverse proxy (e.g. OAuth2 Proxy,
Keycloak Gatekeeper) sits in front of the monitor.

### Fully compatible

These server types use Nagstamon's HTTP session for all requests. The helper
credentials are applied automatically:

- IcingaDBWeb
- IcingaDBWebNotifications
- IcingaWeb2
- Icinga
- Icinga2API
- Nagios
- Thruk
- op5Monitor
- Checkmk Multisite
- Prometheus
- Alertmanager
- Monitos3
- monitos4x
- SNAG-View 3

### Compatible with caveats

These server types use Nagstamon's HTTP session **but also perform their own
API-level authentication**. The helper credentials are sent alongside API
tokens, which works when the auth layer is handled by a reverse proxy in front
of the monitor:

- Zabbix, authenticates via JSON-RPC `auth` field; helper headers are sent
  but Zabbix itself ignores them unless a proxy validates them
- Opsview, authenticates via `X-Opsview-Token`; same caveat
- Centreon, authenticates via `X-Auth-Token`; same caveat
- LibreNMS, authenticates via `X-Auth-Token`; same caveat
- Sensu, uses a separate `SensuAPI` client; helper headers land on the session
  but Sensu API calls go through their own transport

### Not compatible

These server types bypass HTTP entirely or use independent transport:

- Livestatus, communicates via raw TCP sockets, not HTTP
- SensuGo, uses its own `SensuGoAPI` HTTP client, not `fetch_url()`
- Zenoss, uses its own `ZenossAPI` client, not `fetch_url()`


## Configuration

Users configure these fields per server in Nagstamon settings:

| Field | Description | Example |
|---|---|---|
| Helper command | The command to invoke | `nagstamon-oidc-helper` |
| Extra arguments | Appended to the `authenticate` invocation | `--client-id nagstamon --redirect-port 12345` |

The helper command is split by shell rules (supports paths with spaces if quoted).
Extra arguments are also split by shell rules and appended to the `authenticate`
subcommand. Use this to pass helper-specific options like OIDC client IDs,
redirect ports, or any other parameters your helper needs.


## Subcommand: `get-headers`

**Purpose:** Return HTTP headers and/or cookies as JSON. Called non-interactively
on every polling cycle.

### Invocation

```
<command> get-headers --server-name <name>
```

| Argument | Required | Description |
|---|---|---|
| `--server-name` | Yes | Unique server name (as configured in Nagstamon) |

### Success (exit code 0)

Print a JSON object to **stdout**. Two formats are supported:

**Structured format (recommended)**, return headers and/or cookies:

```json
{
  "headers": {"Authorization": "Bearer eyJhbGciOi..."},
  "cookies": {"KEYCLOAK_SESSION": "abc123", "Icingaweb2": "xyz789"}
}
```

**Flat format**, return headers only (treated as a headers-only response):

```json
{"Authorization": "Bearer eyJhbGciOi...", "X-OAuth2": "1"}
```

Requirements:
- Must be a valid JSON object
- In structured format: `headers` is required, `cookies` is optional
- In flat format: the entire object is treated as HTTP headers
- Nagstamon merges headers into `session.headers` and cookies into
  `session.cookies`

### Re-authentication needed (exit code 1)

Signals that tokens are missing, expired, or refresh failed. Nagstamon will
automatically call the `authenticate` subcommand.

Stdout may optionally contain:
```json
{"status": "error", "error": "No tokens found, run 'authenticate' first"}
```

### Other errors (exit code 2+)

Any other exit code is treated as a configuration or infrastructure error.
Nagstamon will display the error and retry on the next cycle.


## Subcommand: `authenticate`

**Purpose:** Perform interactive authentication (e.g. open a browser for OIDC login).
Called automatically when `get-headers` returns exit code 1.

### Invocation

```
<command> authenticate --server-name <name> --monitor-url <url> [<extra-args>...] [--insecure]
```

Nagstamon always passes `--server-name` and `--monitor-url`. Any extra arguments
configured in the server settings are appended. `--insecure` is added when
"Ignore SSL/TLS certificate" is checked.

| Argument | Source | Description |
|---|---|---|
| `--server-name` | Always | Unique server name (for token storage) |
| `--monitor-url` | Always | Monitor server base URL |
| `<extra-args>` | Server config | User-configured extra arguments (e.g. `--client-id`, `--redirect-port`) |
| `--insecure` | Auto | Present when TLS verification is disabled |

### Success (exit code 0)

Print a JSON status to **stdout**:

```json
{"status": "ok", "expires_at": 1773658714}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` on success |
| `expires_at` | number | Unix timestamp when the token expires (informational) |

After success, Nagstamon retries `get-headers` which should now return valid
credentials.

### Failure (exit code 1)

Authentication was cancelled or failed:

```json
{"status": "error", "error": "Timeout waiting for browser login"}
```

### Configuration error (exit code 2)

Discovery or setup failed:

```json
{"status": "error", "error": "Could not discover OIDC provider"}
```


## Verbose / Debug Output

The helper should write debug/verbose output to **stderr** only. Nagstamon captures
stdout for JSON parsing. When Nagstamon is in debug mode, stderr output from the
helper is logged.


## Timeout

Nagstamon sets a subprocess timeout of **180 seconds** for both subcommands. The
`authenticate` command should implement its own timeout for the interactive flow,
typically 120 seconds, and exit with code 1 if it expires.


## Token / Credential Storage

Credential persistence is the helper's responsibility. Nagstamon does not store
or manage tokens, it only consumes the headers and cookies returned by
`get-headers`.

A recommended location is `~/.config/nagstamon-auth/<server-name>.json` with
`0600` file permissions.


## Lifecycle Summary

```
Nagstamon polling cycle
  │
  ├─ Call: <command> get-headers --server-name "my-server"
  │
  ├─ Exit 0 ──► Parse JSON ──► Apply headers + cookies to session ──► Poll monitor
  │
  └─ Exit 1 ──► Call: <command> authenticate --server-name "my-server" \
  │                    --monitor-url "https://..." <extra-args>
  │
  │             ├─ Exit 0 ──► Retry get-headers ──► Continue polling
  │             └─ Exit 1/2 ──► Show error ──► Retry next cycle
  │
  └─ Exit 2+ ──► Show error ──► Retry next cycle
```


## Example Implementation

A complete, self-contained OIDC auth helper is included in
[example-auth-helper/nagstamon-auth-helper](example-auth-helper/nagstamon-auth-helper).
It implements Authorization Code + PKCE via the system browser and can be used
as-is or as a starting point for custom helpers.

Nagstamon configuration:
- **Helper command:** `python3 /path/to/nagstamon-auth-helper`
- **Extra arguments:** `--client-id nagstamon --redirect-port 12345`

