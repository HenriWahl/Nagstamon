# LibreNMS Integration for Nagstamon

This integration allows Nagstamon to monitor alerts from LibreNMS network monitoring system.

## Features

- ✅ Real-time alert monitoring from LibreNMS
- ✅ Display active and acknowledged alerts
- ✅ Acknowledge alerts directly from Nagstamon
- ✅ View alert duration and status
- ✅ Click to open alerts in LibreNMS web interface
- ✅ Standard Nagstamon filtering and notification support

## Requirements

- LibreNMS server with API access
- LibreNMS API token (v0 API)
- Nagstamon 3.x with this integration

## Setup

### 1. Generate LibreNMS API Token

In your LibreNMS web interface:
1. Go to your user profile (top right)
2. Navigate to **API Settings** or **API Access**
3. Click **Create Token**
4. Copy the generated token

### 2. Configure Nagstamon

1. Open Nagstamon
2. Go to **Settings** → **Servers** → **New Server**
3. Configure the server:
   - **Name**: Your server name (e.g., "My LibreNMS")
   - **Type**: Select **LibreNMS** from dropdown
   - **Monitor URL**: Your LibreNMS URL (e.g., `https://librenms.example.com`)
   - **Username**: Leave empty (not used)
   - **Password**: Paste your API token
   - **Enabled**: Check this box
4. Click **OK** to save

### 3. Test Connection

- Nagstamon should now connect to your LibreNMS server
- Active alerts will appear in the Nagstamon interface
- Check the status bar to verify connection

## Usage

### Viewing Alerts

- Alerts appear as services under their respective devices (hosts)
- Each alert shows:
  - Device hostname
  - Alert ID
  - Status (CRITICAL/WARNING)
  - Duration since alert triggered
  - Acknowledged state

### Acknowledging Alerts

1. Right-click on an alert
2. Select **Acknowledge**
3. Add an optional note
4. The alert will be marked as acknowledged in LibreNMS

### Opening in Browser

- Right-click an alert and select **Monitor** to open the specific alert in LibreNMS
- Or click the browser button to open the main alerts page

## API Endpoints Used

The integration uses the following LibreNMS API v0 endpoints:

- `GET /api/v0/alerts` - Fetch all alerts
- `PUT /api/v0/alerts/:id` - Acknowledge specific alert

## Status Mapping

LibreNMS alert states are mapped to Nagstamon statuses:

| LibreNMS State | Nagstamon Status |
|----------------|------------------|
| 0 (ok)         | Hidden (OK)      |
| 1 (alert)      | CRITICAL         |
| 2 (acknowledged) | WARNING (visible but ack'd) |

## Files Modified/Created

### New Files
- `Nagstamon/servers/LibreNMS.py` - Main integration code

### Modified Files
- `Nagstamon/servers/__init__.py` - Registered LibreNMS server type

## Implementation Details

### Architecture

The integration extends `GenericServer` class and follows the same pattern as other Nagstamon server integrations (Prometheus, Zabbix, etc.).

### Key Methods

- `_get_status()` - Fetches alerts from LibreNMS API
- `_get_device_display_name()` - Retrieves friendly device names from LibreNMS
- `_get_service_details()` - Matches alerts with services for detailed messages
- `_set_acknowledge()` - Acknowledges alerts via PUT request
- `_calculate_duration()` - Calculates human-readable alert duration
- `open_monitor()` - Opens alerts in web browser

### Alert Types

LibreNMS has two types of alerts that are handled differently:

1. **Metric-based alerts** - Built-in monitoring (SNMP, device state, sensors, etc.)
   - Example: "Partition used space is >= 90%", "Device is down"
   - No associated service in LibreNMS services API
   - Status info comes from alert's `info`, `proc`, and `notes` fields

2. **Service-based alerts** - User-defined checks (NRPE, custom scripts, etc.)
   - Example: "VEEAM backup failed", "SQL query check"
   - Has matching service in LibreNMS services API
   - Status info enriched with detailed `service_message` field

The integration automatically detects which type each alert is and displays the most relevant information.

### Authentication

LibreNMS API token is passed via the `X-Auth-Token` HTTP header on all API requests.

## Troubleshooting

### Connection Issues

**Problem**: "Cannot connect to server" or authentication errors

**Solutions**:
- Verify your LibreNMS URL is correct and accessible
- Check that your API token is valid (test with `curl`)
- Ensure LibreNMS API is enabled
- Test manually:
  ```bash
  curl -H 'X-Auth-Token: YOUR_TOKEN' https://librenms.example.com/api/v0/alerts
  ```

### No Alerts Showing

**Problem**: Connected but no alerts appear

**Possible causes**:
- No active alerts in LibreNMS (state != 0)
- Alerts are filtered by Nagstamon filter settings
- API permissions issue

**Debug**:
- Enable debug mode in Nagstamon settings
- Check logs for API responses
- Verify alerts exist in LibreNMS web interface

### SSL/TLS Errors

**Problem**: Certificate verification errors

**Solutions**:
- In Nagstamon server settings, enable "Ignore certificate errors" for testing
- For production, add your CA certificate to system trust store
- Or specify custom CA certificate in server settings

## Testing with curl

Test your LibreNMS API access:

```bash
# List all alerts
curl -H 'X-Auth-Token: YOUR_TOKEN' \
  https://librenms.example.com/api/v0/alerts

# Get specific alert
curl -H 'X-Auth-Token: YOUR_TOKEN' \
  https://librenms.example.com/api/v0/alerts/1

# Acknowledge alert
curl -X PUT \
  -H 'X-Auth-Token: YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"note": "Working on it"}' \
  https://librenms.example.com/api/v0/alerts/1
```

## Known Limitations

- Currently does not support unmuting alerts
- Alert severity mapping is simplified (no granular severity levels)
- Downtime/maintenance mode not yet implemented
- Some LibreNMS-specific features may not be exposed

## Future Enhancements

Potential improvements for future versions:

- [ ] Support for alert rule details
- [ ] Device-level information and status
- [ ] Alert filtering by severity in settings
- [ ] Support for unmuting alerts
- [ ] Downtime scheduling support
- [ ] More detailed status information from alert rules

## Contributing

If you want to contribute this integration back to the Nagstamon project:

1. Fork the Nagstamon repository
2. Create a feature branch
3. Submit a pull request with these changes
4. Reference the LibreNMS API documentation

## References

- [LibreNMS API Documentation](https://docs.librenms.org/API/)
- [Nagstamon Project](https://nagstamon.de)
- [Nagstamon GitHub](https://github.com/HenriWahl/Nagstamon)

## License

This integration follows Nagstamon's GPLv2 license.

## Author

Created: 2025-11-06
Integration developed for Nagstamon monitoring desktop application.
