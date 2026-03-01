import sys
import json
import re

from datetime import datetime, timedelta, timezone

from Nagstamon.config import conf
from Nagstamon.objects import (GenericHost, Result)
from Nagstamon.servers.Generic import GenericServer
from Nagstamon.helpers import webbrowser_open

from .helpers import (start_logging,
                      get_duration,
                      convert_timestring_to_utc,
                      detect_from_labels)

from .alertmanagerservice import AlertmanagerService

# TODO: support debug level switching while running
log = start_logging('alertmanager', conf.debug_mode)

class AlertmanagerServer(GenericServer):
    """
    special treatment for alertmanager API
    """
    TYPE = 'Alertmanager'

    # alertmanager actions are limited to visiting the monitor for now
    MENU_ACTIONS = ['Monitor', 'Downtime', 'Acknowledge']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/#/alerts',
        'hosts':    '$MONITOR$/#/alerts',
        'services': '$MONITOR$/#/alerts',
        'history':  '$MONITOR$/#/alerts'
    }

    API_PATH_ALERTS = "/api/v2/alerts?inhibited=false"
    API_PATH_SILENCES = "/api/v2/silences"
    API_FILTERS = '&filter='

    # vars specific to alertmanager class
    map_to_hostname = ''
    map_to_servicename = ''
    map_to_status_information = ''
    map_to_critical = ''
    map_to_warning = ''
    map_to_down = ''
    map_to_unknown = ''
    map_to_ok = ''
    name = ''
    alertmanager_filter = ''


    def init_http(self):
        """
        things to do if HTTP is not initialized
        """
        GenericServer.init_http(self)

        # prepare for JSON
        if self.session is not None:
            self.session.headers.update({'Accept': 'application/json',
                                         'Content-Type': 'application/json'})


    def init_config(self):
        """
        dummy init_config, called at thread start
        """


    def get_start_end(self, host):
        """
        Set a default of starttime of "now" and endtime is "now + 24 hours"
        directly from web interface
        """
        start = datetime.now()
        end = datetime.now() + timedelta(hours=24)

        return (str(start.strftime("%Y-%m-%d %H:%M:%S")),
                str(end.strftime("%Y-%m-%d %H:%M:%S")))

    def map_severity(self, the_severity):
        """Maps a severity

        Args:
            the_severity (str): The severity that should be mapped

        Returns:
            str: The matched Nagstamon severity
        """
        if the_severity in self.map_to_unknown.split(','):
            return "UNKNOWN"
        if the_severity in self.map_to_critical.split(','):
            return "CRITICAL"
        if the_severity in self.map_to_warning.split(','):
            return "WARNING"
        if the_severity in self.map_to_down.split(','):
            return "DOWN"
        if the_severity in self.map_to_ok.split(','):
            return "OK"
        return the_severity.upper()

    def _process_alert(self, alert):
        result = {}

        # alertmanager specific extensions
        generator_url = alert.get("generatorURL", {})
        fingerprint = alert.get("fingerprint", {})
        log.debug("processing alert with fingerprint '%s':", fingerprint)

        labels = alert.get("labels", {})
        state = alert.get("status", {"state": "active"})["state"]
        severity = self.map_severity(labels.get("severity", "unknown"))

        # skip alerts with none severity
        if severity == "NONE":
            log.debug("[%s]: detected detected state '%s' and severity '%s' from labels \
                      -> skipping alert", fingerprint, state, severity)
            return False
        log.debug("[%s]: detected detected state '%s' and severity '%s' from labels",
                  fingerprint, state, severity)

        hostname = detect_from_labels(labels,self.map_to_hostname,"unknown")
        hostname = re.sub(':[0-9]+', '', hostname)
        log.debug("[%s]: detected hostname from labels: '%s'", fingerprint, hostname)

        servicename = detect_from_labels(labels,self.map_to_servicename,"unknown")
        log.debug("[%s]: detected servicename from labels: '%s'", fingerprint, servicename)

        if "status" in alert:
            attempt = alert["status"].get("state", "unknown")
        else:
            attempt = "unknown"

        if attempt == "suppressed":
            scheduled_downtime = True
            acknowledged = True
            log.debug("[%s]: detected status: '%s' -> interpreting as silenced",
                      fingerprint, attempt)
        else:
            scheduled_downtime = False
            acknowledged = False
            log.debug("[%s]: detected status: '%s'", fingerprint, attempt)

        duration = str(get_duration(alert["startsAt"]))

        annotations = alert.get("annotations", {})
        status_information = detect_from_labels(annotations,self.map_to_status_information,'')

        result['host'] = str(hostname)
        result['name'] = servicename
        result['server'] = self.name
        result['status'] = severity
        result['labels'] = labels
        result['last_check'] = str(get_duration(alert["updatedAt"]))
        result['attempt'] = attempt
        result['scheduled_downtime'] = scheduled_downtime
        result['acknowledged'] = acknowledged
        result['duration'] = duration
        result['generatorURL'] = generator_url
        result['fingerprint'] = fingerprint
        result['status_information'] = status_information

        return result


    def _get_status(self):
        """
        Get status from alertmanager Server
        """

        log.debug("detection config (map_to_status_information): '%s'",
                  self.map_to_status_information)
        log.debug("detection config (map_to_hostname): '%s'",
                  self.map_to_hostname)
        log.debug("detection config (map_to_servicename): '%s'",
                  self.map_to_servicename)
        log.debug("detection config (alertmanager_filter): '%s'",
                  self.alertmanager_filter)
        log.debug("severity config (map_to_unknown): '%s'",
                  self.map_to_unknown)
        log.debug("severity config (map_to_critical): '%s'",
                  self.map_to_critical)
        log.debug("severity config (map_to_warning): '%s'",
                  self.map_to_warning)
        log.debug("severity config (map_to_down): '%s'",
                  self.map_to_down)
        log.debug("severity config (map_to_ok): '%s'",
                  self.map_to_ok)

        # get all alerts from the API server
        try:
            if self.alertmanager_filter != '':
                result = self.fetch_url(self.monitor_url + self.API_PATH_ALERTS + self.API_FILTERS
                                        + self.alertmanager_filter, giveback="raw")
            else:
                result = self.fetch_url(self.monitor_url + self.API_PATH_ALERTS,
                                        giveback="raw")

            if result.status_code == 200:
                log.debug("received status code '%s' with this content in result.result: \n\
                           ---------------------------------------------------------------\n\
                           %s\
                           ---------------------------------------------------------------",
                           result.status_code, result.result)
            else:
                log.error("received status code '%s'", result.status_code)

            try:
                data = json.loads(result.result)
            except json.decoder.JSONDecodeError:
                data = {}
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return errors_occured

            for alert in data:
                alert_data = self._process_alert(alert)
                if not alert_data:
                    continue

                service = AlertmanagerService()
                service.host = alert_data['host']
                service.name = alert_data['fingerprint']
                service.display_name = alert_data['name']
                service.server = alert_data['server']
                service.status = alert_data['status']
                service.labels = alert_data['labels']
                service.scheduled_downtime = alert_data['scheduled_downtime']
                service.acknowledged = alert_data['acknowledged']
                service.last_check = alert_data['last_check']
                service.attempt = alert_data['attempt']
                service.duration = alert_data['duration']

                service.generator_url = alert_data['generatorURL']
                service.fingerprint = alert_data['fingerprint']

                service.status_information = alert_data['status_information']

                if service.host not in self.new_hosts:
                    self.new_hosts[service.host] = GenericHost()
                    self.new_hosts[service.host].name = str(service.host)
                    self.new_hosts[service.host].server = self.name
                self.new_hosts[service.host].services[service.name] = service

        except Exception as the_exception:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            log.exception(the_exception)
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def open_monitor_webpage(self, host, service):
        """
        open monitor from tablewidget context menu
        """
        webbrowser_open('%s' % (self.monitor_url))

    def open_monitor(self, host, service):
        """
        open monitor for alert
        """
        url = self.monitor_url
        webbrowser_open(url)


    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):

        # Services are keyed by fingerprint internally, but the UI passes display_name.
        # Look up the alert by display_name.
        alert = next((s for s in self.hosts[host].services.values()
                      if s.display_name == service), None)
        if alert is None:
            log.error(f'_set_downtime: service "{service}" not found on host "{host}"')
            return

        # Convert local dates to UTC
        start_time_dt = convert_timestring_to_utc(start_time)
        end_time_dt = convert_timestring_to_utc(end_time)

        # API Spec: https://github.com/prometheus/alertmanager/blob/master/api/v2/openapi.yaml
        silence_data = {}
        silence_data["matchers"] = []
        for name, value in alert.labels.items():
            silence_data["matchers"].append({
                "name": name,
                "value": value,
                "isRegex": False,
                "isEqual": True
            })
        silence_data["startsAt"] = start_time_dt
        silence_data["endsAt"] = end_time_dt
        silence_data["comment"] = comment or "Nagstamon downtime"
        silence_data["createdBy"] = author or "Nagstamon"

        self.fetch_url(self.monitor_url + self.API_PATH_SILENCES, giveback="raw",
                       cgi_data=json.dumps(silence_data))


    # Overwrite function from generic server to add expire_time value
    def set_acknowledge(self, info_dict):
        '''
            different monitors might have different implementations of _set_acknowledge
        '''
        if info_dict['acknowledge_all_services'] is True:
            all_services = info_dict['all_services']
        else:
            all_services = []

        # Make sure expire_time is set
        #if not info_dict['expire_time']:
        #    info_dict['expire_time'] = None

        self._set_acknowledge(info_dict['host'],
                              info_dict['service'],
                              info_dict['author'],
                              info_dict['comment'],
                              info_dict['sticky'],
                              info_dict['notify'],
                              info_dict['persistent'],
                              all_services,
                              info_dict['expire_time'])


    def _post_silence(self, alert, author, comment, starts_at, ends_at):
        """Build and POST a silence payload for the given alert object."""
        silence_data = {
            "matchers": [
                {"name": name, "value": value, "isRegex": False}
                for name, value in alert.labels.items()
            ],
            "startsAt": starts_at,
            "endsAt": ends_at,
            "comment": comment or "Nagstamon silence",
            "createdBy": author or "Nagstamon",
        }
        return self.fetch_url(self.monitor_url + self.API_PATH_SILENCES, giveback="raw",
                              cgi_data=json.dumps(silence_data))

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent,
                         all_services=None, expire_time=None):
        # Services are keyed by fingerprint internally, but the UI passes display_name.
        # Look up the alert by display_name.
        alert = next((s for s in self.hosts[host].services.values()
                      if s.display_name == service), None)
        if alert is None:
            log.error(f'_set_acknowledge: service "{service}" not found on host "{host}"')
            return

        starts_at = datetime.now(timezone.utc).isoformat()
        ends_at = convert_timestring_to_utc(expire_time) if expire_time else starts_at

        self._post_silence(alert, author, comment, starts_at, ends_at)

        if all_services:
            for svc_name in all_services:
                svc_alert = next((s for s in self.hosts[host].services.values()
                                  if s.display_name == svc_name), None)
                if svc_alert is None:
                    log.error(f'_set_acknowledge: service "{svc_name}" not found on host "{host}"')
                    continue
                self._post_silence(svc_alert, author, comment, starts_at, ends_at)
