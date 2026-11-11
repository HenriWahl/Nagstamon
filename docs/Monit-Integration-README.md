# Monit

Choose **Monit** as the server type in Nagstamon. Set the monitor URL to the
Monit HTTP server, for example `https://server.example.com:2812`, and select
Basic authentication with the username and password configured in Monit.
No separate CGI URL is needed. The standard Nagstamon TLS and proxy settings
apply. An existing Monit read-only HTTP account is sufficient.

The integration polls `/_status?format=xml`. Each configured Monit check
(process, file, filesystem, network, program, system resources, etc.) appears
as a service under the hostname reported by Monit. Add one Nagstamon server
entry for each Monit instance; this integration does not use M/Monit.

Status mapping:

| Monit state | Nagstamon state |
| --- | --- |
| No errors | OK |
| Failed checks | CRITICAL |
| Changes only (`status_hint`) | WARNING |
| Not monitored, initializing, waiting | UNKNOWN |

Unmonitored checks respect Nagstamon's disabled-check filter. Monit's passive
mode still performs checks and is not treated as disabled monitoring.
System resource failures remain service problems, rather than marking the host
down. Connection and authentication failures are reported as server errors.
Monit does not provide a last-state-change timestamp in this status response,
so the duration column is left empty.

**Monitor** opens the selected check in Monit's web interface. Acknowledgment,
downtime, and remote control actions are not provided by this integration.
