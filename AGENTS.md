# Contributing as an AI Agent to Nagstamon

Nagstamon is a cross-platform PyQt6/Qt5 desktop monitoring application that aggregates status from 20+ monitoring systems (Nagios, Icinga, Zabbix, Prometheus, etc.). This guide helps AI agents understand the codebase structure and development workflows.

## Architecture Overview

**Three-tier structure:**
1. **Configuration Layer** (`Nagstamon/config.py`): Central settings hub, loaded once at startup. Manages cross-platform specifics (Linux/macOS/Windows, desktop environments, Wayland).
2. **Server Plugin System** (`Nagstamon/servers/`): Each monitoring system (Nagios, Icinga, Zabbix, etc.) extends `GenericServer`. Uses dynamic registration pattern via `SERVER_TYPES` dict and `register_server()`.
3. **PyQt6 GUI Layer** (`Nagstamon/qui/`): Qt widgets, dialogs, system tray integration. Imports gui modules cause Qt initialization—avoid in non-gui code.

**Data Flow:**
- `nagstamon.py` (entry point) → `Nagstamon.qui` (GUI app) → `Nagstamon.servers` (status fetching)
- Configuration flows from `config.py` to all server instances
- Status objects (`GenericHost`, `GenericService` in `objects.py`) unify data from all server types

## Server Integration Pattern

**Adding a new monitoring system requires:**

1. Create `Nagstamon/servers/YourServer.py` extending `GenericServer`
2. Register in `Nagstamon/servers/__init__.py` by adding to `servers_list` and importing
3. Implement core methods:
   - `init_http()`: Initialize session headers/auth
   - `get_status()`: Fetch and parse status, populate `self.hosts` and `self.services`
   - `_set_recheck()`, `_acknowledge()`: Actions (optional)

**Key patterns:**
- Server configuration accessed via `conf.servers[self.get_name()]`
- Use `self.session` (from `GenericServer`) for HTTP; add headers in `init_http()`
- Status parsing stores result in `self.hosts` and `self.services` dicts (keyed by host/service name)
- Parse into `GenericHost`/`GenericService` objects with standard fields: `name`, `status` ('UP'/'DOWN'/'OK'/'CRITICAL'/etc.), `status_information`, `acknowledged`, `scheduled_downtime`, `flapping`

**Examples:**
- `Nagios.py`: Classic CGI API parsing
- `Centreon/__init__.py`: Proxy pattern (detects version, switches to `CentreonLegacy` or `CentreonModern`)
- `Alertmanager/alertmanagerserver.py`: JSON REST API with custom mapping fields (`map_to_hostname`, `map_to_status`)

## Testing Pattern

**Three test strategies** (see `tests/test_smoke.py`):

1. **Non-GUI modules** (config, servers, helpers): Full import via `importlib` - catches all runtime errors
2. **GUI modules** (Nagstamon/qui/**): Syntax-only via `py_compile` - requires display/Qt, skipped in headless CI
3. **Vendored Xlib**: Syntax-only (avoid version mismatch errors with system python-xlib)

**Run tests:**
```bash
python -m pytest tests/
```

## Configuration & Cross-Platform Handling

**Key config patterns:**
- Multiple config folder support (`conf.configdir`, `nagstamon.conf`, `nagstamon2.conf/`)
- OS detection: `from Nagstamon.config import OS, OS_WINDOWS, OS_MACOS`
- Desktop environment handling: `DESKTOP_WAYLAND`, `DESKTOP_NEEDS_FIX` for quirky desktops
- Keyring support (optional, disabled on some KDE+Ubuntu combos to avoid segfaults)

**Configuration object** (`conf` singleton from `config.py`):
- `conf.servers` (OrderedDict of server configs)
- `conf.debug_mode` (debug logging)
- `conf.update_interval_seconds` (polling frequency)
- Authentication state and SSL/TLS per server

## Build System

**Multi-platform builds** (see `build/build.py`):
- **Windows**: PyInstaller → exe (optional code signing)
- **macOS**: PyInstaller → app bundle or DMG
- **Linux**: 
  - Debian/Ubuntu via `setup.py` + debuild
  - RPM via `setup.py bdist_rpm`
  - DockerFiles for multiple distros (Fedora 41-45, RHEL 9, Debian)

**Dependencies** managed platform-specifically:
- Qt6 preferred on newer systems; Qt5 fallback on older Fedora/RHEL
- Check `build/requirements/{linux,macos,windows}.txt`

## Common Development Tasks

**Running locally:**
```bash
python nagstamon.py
```

**Debugging GUI issues:**
- GUI requires display; use `--help` to check environment
- Set `conf.debug_mode = True` in config for server debug output

**Modifying server status parsing:**
- Edit `get_status()` method
- Test via smoke tests: `python -m pytest tests/test_smoke.py`
- Populate `self.hosts` and `self.services` with correct status strings from `helpers.STATES`

**Adding server config options:**
- Add to server class via `__init__()` defaults
- Add UI widget in `Nagstamon/qui/dialogs/server.py` `VOLATILE_WIDGETS` dict (shown/hidden per server type)
- Persist via `create_server()` in `servers/__init__.py`

## State Values & Severity

**Standard status strings** (`helpers.STATES`):
- Severity order (worst to least): `DISASTER > CRITICAL > DOWN > HIGH > AVERAGE > WARNING > UNKNOWN > INFORMATION > UP`
- Different servers use different names; always normalize to above set
- Example: Zabbix "Disaster" → `DISASTER`, Prometheus AlertManager severity mapping in `map_to_*` fields

## Important Conventions

1. **No circular imports**: GUI modules import server/config; config/servers must NOT import gui. Break cycles via local imports if needed.
2. **Lock mechanism**: Single-instance check at startup via `lock_config_folder()` prevents concurrent runs on same config
3. **Thread lifecycle**: Servers run in update threads; status fetching must be thread-safe, avoid gui imports
4. **Debug infrastructure**: Use `self.debug(server=name, debug=msg)` for logging, routed to `debug_queue` if enabled
5. **Error handling**: Catch exceptions in `get_status()`, return `Result(result=result_code, error=error_msg)` for graceful degradation

## Key Files Reference

- `Nagstamon/config.py` (1248 lines): AppInfo, OS detection, conf singleton, RESOURCES paths
- `Nagstamon/servers/Generic.py` (1800 lines): Base class with HTTP handling, status aggregation, action methods
- `Nagstamon/servers/__init__.py`: Plugin registration, server instantiation, aggregation functions
- `Nagstamon/objects.py`: `GenericHost`/`GenericService` domain models
- `Nagstamon/qui/__init__.py`: Qt app initialization, system tray setup
- `Nagstamon/helpers.py`: Filtering (regex), STATES constant, utilities

## Debugging Tips

1. Enable debug mode in config to see server refresh logs
2. Check `nagstamon.conf` for server credentials and URLs
3. Use `python -c "import Nagstamon.servers.YourServer; print('OK')"` to test server module imports
4. GUI breakpoints require Qt event loop; print debugging more reliable
5. Check for `ClassServerReal` pattern—some servers proxy to real implementation after detection

