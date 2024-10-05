## Overview
Nagstamon headless mode can be used to query all data fetched by Nagstamon from all enabled servers allowing a unified view of all alerts from all configured servers (just like Nagstamon does on desktop).
The data retrieved from the REST api can then be used for example in Grafana to visualize all open alerts.

## Server passwords
Using Nagstamon in headless mode in containers where no keyring is available the option "Use system keyring" must be disabled for saving the server passwords to the server config files.
Make sure the `password` key is not empty in your servers config.

### Grafana example
Using the datasource plugin [yesoreyeram-infinity-datasource](https://grafana.com/docs/plugins/yesoreyeram-infinity-datasource/latest/) you can visualize all data from the datasource.

#### Datasource configuration
* Authentication
 * Auth type: Basic Authentication
 * User Name: <NAGSTAMON_HEADLESS_BASICAUTH_USER>
 * Password: <NAGSTAMON_HEADLESS_BASICAUTH_PASSWORD>
 * Allowed Hosts: http(s)://<NAGSTAMON_HEADLESS_ADDRESS>[:<NAGSTAMON_HEADLESS_PORT>]
* URL, Headers & Params
 * Base URL: http(s)://<NAGSTAMON_HEADLESS_ADDRESS>[:<NAGSTAMON_HEADLESS_PORT>]
* Health check
 * Enable custom health check: true
 * Health check URL: http(s)://<NAGSTAMON_HEADLESS_ADDRESS>[:<NAGSTAMON_HEADLESS_PORT>]/hosts

#### Grafana Dashboard



## Docker Standalone with same Nagstamon config directory from Windows install
```
docker run -it -p 80:80 -v C:\Users\fries\.nagstamon:/root/.nagstamon:ro -e NAGSTAMON_HEADLESS=true -e NAGSTAMON_HEADLESS_BASICAUTH_USER=nagstamon -e NAGSTAMON_HEADLESS_BASICAUTH_PASSWORD=test friesoft/nagstamon-headless:0.0.1
```

Sample call to REST API:
```
curl http://127.0.0.1:80/hosts -u nagstamon:test
```

## docker compose
```
---
version: '3.9'
services:
  nagstamon-headless:
    container_name: nagstamon-headless
    image: friesoft/nagstamon-headless:0.0.1
    restart: unless-stopped
    volumes:
      - /volume1/docker/nagstamon-headless:/root/.nagstamon:ro
    environment:
      - NAGSTAMON_HEADLESS=true # mandatory
      - NAGSTAMON_HEADLESS_ADDRESS=0.0.0.0 # default value
      - NAGSTAMON_HEADLESS_PORT=80 # default value
      - NAGSTAMON_HEADLESS_BASICAUTH_USER=nagstamon # mandatory
      - NAGSTAMON_HEADLESS_BASICAUTH_PASSWORD=test # mandatory
```