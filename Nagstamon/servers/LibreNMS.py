# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

# LibreNMS integration for Nagstamon
#
# This Server class connects against LibreNMS API.
# The monitor URL in the setup should be something like
# http://librenms.example.com
#
# Authentication: Use API token as password field, username can be empty
# API token can be generated in LibreNMS under: User > API Settings

import sys
import json
from datetime import datetime

from Nagstamon.config import conf
from Nagstamon.objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.servers.Generic import GenericServer
from Nagstamon.helpers import webbrowser_open


class LibreNMSServer(GenericServer):
    """
    special treatment for LibreNMS API
    """
    TYPE = 'LibreNMS'

    # LibreNMS actions
    MENU_ACTIONS = ['Monitor', 'Acknowledge']
    BROWSER_URLS = {
        'monitor': '$MONITOR$',
        'hosts': '$MONITOR$/devices',
        'services': '$MONITOR$/alerts',
        'history': '$MONITOR$/eventlog'
    }

    # API paths
    API_PATH_ALERTS = "/api/v0/alerts"
    API_PATH_DEVICES = "/api/v0/devices"

    # Status mapping from LibreNMS severity to Nagios-style states
    # LibreNMS severities: ok, warning, critical
    SEVERITY_MAPPING = {
        'ok': 'OK',
        'warning': 'WARNING',
        'critical': 'CRITICAL'
    }

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Store device information for alert enrichment
        self.devices = {}

        # Cache for services (by device_id)
        self.services_cache = {}

        # Option to treat service status as alerts
        # When enabled, non-OK services will be shown even without alert rules
        self.treat_services_as_alerts = False

    def init_http(self):
        """
        things to do if HTTP is not initialized
        """
        GenericServer.init_http(self)

        # prepare for JSON and set API token header
        # LibreNMS uses X-Auth-Token header for authentication
        if self.session and hasattr(self.session, 'headers'):
            self.session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Auth-Token': self.password  # API token goes in X-Auth-Token header
            })

    def init_config(self):
        """
        dummy init_config, called at thread start
        """
        pass

    def _get_device_display_name(self, device_id, hostname_fallback):
        """
        Get the display name for a device from cache or API
        """
        # Check if we already have this device cached
        if device_id in self.devices:
            return self.devices[device_id].get('display', hostname_fallback)

        # Fetch device details from API
        try:
            result = self.fetch_url(
                f"{self.monitor_url}/api/v0/devices/{device_id}",
                giveback="json"
            )

            if result.result and result.result.get('status') == 'ok':
                device_data = result.result.get('devices', [{}])[0]
                # Cache the device info
                self.devices[device_id] = device_data

                # Try different fields in order of preference
                # display > sysName > hostname
                display_name = (device_data.get('display') or
                               device_data.get('sysName') or
                               device_data.get('hostname') or
                               hostname_fallback)

                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug=f"Device {device_id}: display='{display_name}' (from {device_data.get('hostname', 'N/A')})")

                return display_name
        except Exception:
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                          debug=f"Could not fetch device {device_id}, using fallback: {hostname_fallback}")

        return hostname_fallback

    def _get_alert_details(self, alert_id):
        """
        Get detailed alert information including rule name
        """
        try:
            result = self.fetch_url(
                f"{self.monitor_url}/api/v0/alerts/{alert_id}",
                giveback="json"
            )

            if result.result and result.result.get('status') == 'ok':
                alerts = result.result.get('alerts', [])
                if alerts:
                    return alerts[0]
        except Exception:
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                          debug=f"Could not fetch alert details for {alert_id}")

        return None

    def _get_rule_name(self, rule_id):
        """
        Get the rule name from cache or API
        """
        # Use a rules cache dictionary
        if not hasattr(self, 'rules_cache'):
            self.rules_cache = {}

        # Check cache first
        if rule_id in self.rules_cache:
            return self.rules_cache[rule_id]

        # Fetch rule details from API
        try:
            result = self.fetch_url(
                f"{self.monitor_url}/api/v0/rules/{rule_id}",
                giveback="json"
            )

            if result.result and result.result.get('status') == 'ok':
                rules = result.result.get('rules', [])
                if rules:
                    rule_name = rules[0].get('name', f'Rule {rule_id}')
                    # Cache it
                    self.rules_cache[rule_id] = rule_name
                    return rule_name
        except Exception:
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                          debug=f"Could not fetch rule {rule_id}")

        return f"Rule {rule_id}"

    def _get_service_details(self, device_id, service_name):
        """
        Find a matching service for the alert and return its details
        Returns service_message if found
        """
        # Check if we have services cached for this device
        if device_id not in self.services_cache:
            # Fetch services for this device
            try:
                result = self.fetch_url(
                    f"{self.monitor_url}/api/v0/services",
                    giveback="json"
                )

                if result.result and result.result.get('status') == 'ok':
                    services = result.result.get('services', [])

                    # Build a device_id -> services mapping
                    for svc_list in services:
                        for svc in svc_list:
                            dev_id = svc.get('device_id')
                            if dev_id not in self.services_cache:
                                self.services_cache[dev_id] = []
                            self.services_cache[dev_id].append(svc)

                    if conf.debug_mode:
                        self.debug(server=self.get_name(),
                                  debug=f"Cached services for all devices")
            except Exception:
                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug=f"Could not fetch services")
                return None

        # Now find matching service by name
        device_services = self.services_cache.get(device_id, [])
        for svc in device_services:
            if svc.get('service_name', '').lower() in service_name.lower() or \
               service_name.lower() in svc.get('service_name', '').lower():
                return svc.get('service_message', '')

        return None

    def _get_status(self):
        """
        Get status from LibreNMS Server
        """
        # Reset new_hosts dictionary
        self.new_hosts = {}

        try:
            # Get alerts from LibreNMS API
            # state=1 means "alert" status (active alerts)
            # We'll get both active (state=1) and acknowledged (state=2) alerts
            result = self.fetch_url(
                self.monitor_url + self.API_PATH_ALERTS,
                giveback="json"
            )

            data = result.result
            error = result.error
            status_code = result.status_code

            # check if any error occurred
            errors_occurred = self.check_for_error(data, error, status_code)
            if errors_occurred is not None:
                return errors_occurred

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                          debug=f"Fetched {len(data.get('alerts', []))} alerts from LibreNMS")

            # Process each alert
            alerts = data.get('alerts', [])

            for alert in alerts:
                # Skip alerts that are in "ok" state (state=0)
                # state: 0=ok, 1=alert, 2=acknowledged
                alert_state = int(alert.get('state', 0))
                if alert_state == 0:
                    continue

                # Get device information
                device_id = alert.get('device_id')
                hostname_raw = alert.get('hostname', f'device_{device_id}')

                # Get the display name from device API (cached)
                hostname = self._get_device_display_name(device_id, hostname_raw)

                # Get alert details
                alert_id = alert.get('id')
                rule_id = alert.get('rule_id')

                # LibreNMS provides a 'name' field - use it directly!
                service_name = alert.get('name', f'Alert {alert_id}')

                # Get timestamp and calculate duration
                timestamp = alert.get('timestamp', '')

                # Get severity directly from alert (warning, critical, ok)
                severity = alert.get('severity', 'unknown').upper()

                # Map LibreNMS severity to Nagstamon status
                status_mapping = {
                    'OK': 'OK',
                    'WARNING': 'WARNING',
                    'CRITICAL': 'CRITICAL',
                    'UNKNOWN': 'UNKNOWN'
                }
                status = status_mapping.get(severity, 'CRITICAL')

                # Build informative status message
                status_parts = []

                # Try to get detailed service message from services API
                # This only works for service-based alerts (NRPE, custom checks)
                # Metric-based alerts won't have a matching service
                service_message = self._get_service_details(device_id, service_name)

                # If we found a matching service, prioritize its detailed message
                if service_message:
                    status_parts.append(f"Service: {service_message}")
                    if conf.debug_mode:
                        self.debug(server=self.get_name(),
                                  debug=f"Found service match for alert {alert_id}: {service_name}")
                else:
                    # No service match - this is likely a metric-based alert
                    # Use alert fields directly
                    if conf.debug_mode:
                        self.debug(server=self.get_name(),
                                  debug=f"No service match for alert {alert_id} - using metric data")

                # Add info field if available (for metric alerts, this is important!)
                alert_info = alert.get('info', '').strip()
                if alert_info and alert_info not in str(service_message):
                    status_parts.append(alert_info)

                # Add proc field if available
                alert_proc = alert.get('proc', '').strip()
                if alert_proc and alert_proc not in str(service_message):
                    status_parts.append(alert_proc)

                # Add notes if available
                alert_notes = alert.get('notes', '').strip()
                if alert_notes:
                    status_parts.append(f"Notes: {alert_notes}")

                # Add acknowledgment note if exists
                alert_note = alert.get('note', '').strip()
                if alert_note:
                    # Just show the last line of the note (most recent)
                    last_note = alert_note.split('\n')[-1] if '\n' in alert_note else alert_note
                    status_parts.append(f"Ack: {last_note}")

                # If we still don't have any info, show timestamp
                if not status_parts and timestamp:
                    status_parts.append(f"Active since {timestamp}")

                # Final fallback
                if not status_parts:
                    status_parts.append(f"Alert ID: {alert_id}")

                status_information = " | ".join(status_parts)

                # Create service object
                service = GenericService()
                service.host = hostname
                service.name = service_name
                service.server = self.name
                service.status = status
                service.last_check = timestamp
                service.duration = self._calculate_duration(timestamp)
                service.attempt = 'n/a'

                # Check if acknowledged (state=2)
                service.acknowledged = (alert_state == 2)

                # Store alert_id for acknowledge operations
                service.real_name = str(alert_id)

                # Set the status information
                service.status_information = status_information

                # Create host if not exists
                if hostname not in self.new_hosts:
                    self.new_hosts[hostname] = GenericHost()
                    self.new_hosts[hostname].name = hostname
                    self.new_hosts[hostname].server = self.name
                    self.new_hosts[hostname].status = 'UP'

                # Add service to host
                self.new_hosts[hostname].services[service_name] = service

                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug=f"Added alert {alert_id} for {hostname}: {service_name}")

            # If "treat services as alerts" is enabled, also add non-OK services
            if self.treat_services_as_alerts:
                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug="Processing services as alerts...")

                self._add_services_as_alerts()

        except Exception:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def _add_services_as_alerts(self):
        """
        Add non-OK services as alerts (when treat_services_as_alerts is enabled)
        This is called after alerts are processed to avoid duplicates
        """
        # Track which device/service combinations we already have from alerts
        existing_alerts = set()
        for hostname, host_obj in self.new_hosts.items():
            for service_name in host_obj.services.keys():
                existing_alerts.add((host_obj.name, service_name))

        # Fetch all services if not cached
        if not self.services_cache:
            try:
                result = self.fetch_url(
                    f"{self.monitor_url}/api/v0/services",
                    giveback="json"
                )

                if result.result and result.result.get('status') == 'ok':
                    services = result.result.get('services', [])
                    for svc_list in services:
                        for svc in svc_list:
                            dev_id = svc.get('device_id')
                            if dev_id not in self.services_cache:
                                self.services_cache[dev_id] = []
                            self.services_cache[dev_id].append(svc)
            except Exception:
                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug="Could not fetch services for treat_services_as_alerts")
                return

        # Process non-OK services
        for device_id, services_list in self.services_cache.items():
            for svc in services_list:
                # Skip OK services (status=0)
                service_status = svc.get('service_status', 0)
                if service_status == 0:
                    continue

                # Skip disabled or ignored services
                if svc.get('service_disabled', 0) == 1 or svc.get('service_ignore', 0) == 1:
                    continue

                # Get device display name
                hostname_raw = f"device_{device_id}"
                hostname = self._get_device_display_name(device_id, hostname_raw)

                service_name_raw = svc.get('service_name', 'Unknown Service')
                # Add marker to distinguish services from alerts
                service_name = f"[S] {service_name_raw}"

                # Check if we already have this from an alert (deduplicate)
                # Use raw name for deduplication check
                if (hostname, service_name_raw) in existing_alerts or (hostname, service_name) in existing_alerts:
                    if conf.debug_mode:
                        self.debug(server=self.get_name(),
                                  debug=f"Skipping duplicate: {hostname}/{service_name}")
                    continue

                # Map service status to Nagstamon status
                status_map = {
                    0: 'OK',
                    1: 'WARNING',
                    2: 'CRITICAL',
                    3: 'UNKNOWN'
                }
                status = status_map.get(service_status, 'UNKNOWN')

                # Create service object
                service = GenericService()
                service.host = hostname
                service.name = service_name
                service.server = self.name
                service.status = status
                service.last_check = 'n/a'
                service.duration = 'n/a'
                service.attempt = 'n/a'
                service.acknowledged = False

                # Use service message as status information
                service.status_information = svc.get('service_message', 'No message')

                # Store service_id for potential future operations
                service.real_name = f"service_{svc.get('service_id')}"

                # Create host if not exists
                if hostname not in self.new_hosts:
                    self.new_hosts[hostname] = GenericHost()
                    self.new_hosts[hostname].name = hostname
                    self.new_hosts[hostname].server = self.name
                    self.new_hosts[hostname].status = 'UP'

                # Add service to host
                self.new_hosts[hostname].services[service_name] = service

                if conf.debug_mode:
                    self.debug(server=self.get_name(),
                              debug=f"Added service as alert: {hostname}/{service_name} ({status})")

    def _calculate_duration(self, timestamp):
        """
        Calculate duration from timestamp to now
        timestamp format from LibreNMS: "2014-12-11 14:40:02"
        """
        try:
            if not timestamp:
                return "n/a"

            # Parse timestamp
            alert_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            duration = now - alert_time

            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            seconds = duration.seconds % 60

            if days > 0:
                return f"{days}d {hours}h {minutes:02d}m"
            elif hours > 0:
                return f"{hours}h {minutes:02d}m {seconds:02d}s"
            elif minutes > 0:
                return f"{minutes}m {seconds:02d}s"
            else:
                return f"{seconds}s"
        except Exception:
            return "n/a"

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        """
        Acknowledge an alert in LibreNMS
        """
        try:
            # Find the alert ID from the service
            if host in self.hosts and service in self.hosts[host].services:
                service_obj = self.hosts[host].services[service]
                alert_id = service_obj.real_name

                # LibreNMS acknowledge endpoint: PUT /api/v0/alerts/:id
                url = f"{self.monitor_url}/api/v0/alerts/{alert_id}"

                # Prepare acknowledge data
                # note and until_clear are optional parameters
                data = {}
                if comment:
                    data['note'] = comment
                # until_clear: if false, alert will re-alert if it changes
                # We'll set to false by default for Nagstamon behavior
                data['until_clear'] = False

                # Make PUT request using session directly
                # since fetch_url doesn't support PUT method
                # The session already has verify setting from init_http()
                if self.session:
                    response = self.session.put(
                        url,
                        json=data,
                        timeout=self.timeout,
                        verify=self.session.verify  # Explicitly use session's verify setting
                    )

                    if conf.debug_mode:
                        self.debug(server=self.get_name(),
                                  debug=f"Acknowledged alert {alert_id}: status {response.status_code}")

                    # Check for errors
                    if response.status_code >= 400:
                        error_msg = f"Failed to acknowledge alert {alert_id}: HTTP {response.status_code}"
                        self.error(error_msg)
                        return Result(result=False, error=error_msg)

        except Exception:
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        return Result()

    def open_monitor(self, host, service=''):
        """
        open monitor for specific alert
        """
        if service and host in self.hosts and service in self.hosts[host].services:
            service_obj = self.hosts[host].services[service]
            alert_id = service_obj.real_name
            url = f"{self.monitor_url}/alerts/{alert_id}"
        else:
            # Open general alerts page
            url = f"{self.monitor_url}/alerts"

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                      debug=f"Opening monitor web page {url}")

        webbrowser_open(url)

    def open_monitor_webpage(self):
        """
        open monitor from systray/toparea context menu
        """
        if conf.debug_mode:
            self.debug(server=self.get_name(),
                      debug=f"Opening monitor web page {self.monitor_url}")
        webbrowser_open(self.monitor_url)
