# alertmanager

## description
The AlertmanagerServer and AlertmanagerService classes implement support for Prometheus' alertmanager.

The monitor URL in the setup should be something like:
`http://prometheus.example.com:9093`

What the integration does:

It reads the alerts from the Alertmanager's REST API and tries to fit each alert into Nagstamon's GenericServer and GenericService objects.

## author(s)
Initial implementation by Stephan Schwarz (@stearz)