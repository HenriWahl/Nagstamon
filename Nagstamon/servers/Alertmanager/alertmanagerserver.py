import sys
import json
import re

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from Nagstamon.config import conf
from Nagstamon.objects import (GenericHost, Result)
from Nagstamon.servers.Generic import GenericServer
from Nagstamon.helpers import webbrowser_open

from .helpers import (start_logging,
                      add_duration_to_timestring,
                      get_duration,
                      convert_timestring_to_utc,
                      detect_from_labels,
                      split_matchers)

from .alertmanagerservice import AlertmanagerService

# TODO: support debug level switching while running
log = start_logging('alertmanager', conf.debug_mode)

class AlertmanagerServer(GenericServer):
    """
    special treatment for alertmanager API
    """
    TYPE = 'Alertmanager'

    # acknowledgement and downtime are both mapped onto silences
    MENU_ACTIONS = ['Monitor', 'Downtime', 'Acknowledge']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/#/alerts',
        'hosts':    '$MONITOR$/#/alerts',
        'services': '$MONITOR$/#/alerts',
        'history':  '$MONITOR$/#/alerts'
    }

    API_PATH_ALERTS = "/api/v2/alerts"
    API_PATH_SILENCES = "/api/v2/silences"
    API_PATH_SILENCE = "/api/v2/silence"

    # how long a silence lasts which was created by an acknowledgement without expiry time
    DEFAULT_SILENCE_HOURS = 24

    # Alertmanager only knows silences, so the comment tells afterwards whether a silence
    # was meant as an acknowledgement or as a downtime
    SILENCE_COMMENT_ACKNOWLEDGE = 'Nagstamon acknowledgement'
    SILENCE_COMMENT_DOWNTIME = 'Nagstamon downtime'

    # states an alert severity can be mapped to, worst first
    # these are the states GenericServer.get_status() counts for services, plus OK, which
    # makes an alert disappear, and the deprecated DOWN, which only hosts can be in
    SEVERITY_MAP_OPTIONS = ('disaster',
                            'critical',
                            'down',
                            'high',
                            'average',
                            'warning',
                            'information',
                            'unknown',
                            'ok')

    # states a service can really be in - anything else is never counted and would make an
    # alert vanish without a trace
    SERVICE_STATES = ('DISASTER',
                      'CRITICAL',
                      'HIGH',
                      'AVERAGE',
                      'WARNING',
                      'INFORMATION',
                      'UNKNOWN',
                      'OK')

    # vars specific to alertmanager class
    map_to_hostname = ''
    map_to_servicename = ''
    map_to_status_information = ''
    map_to_critical = ''
    map_to_warning = ''
    map_to_down = ''
    map_to_unknown = ''
    map_to_ok = ''
    map_to_disaster = ''
    map_to_high = ''
    map_to_average = ''
    map_to_information = ''
    name = ''
    alertmanager_filter = ''
    silence_matcher_labels = ''


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
        """Maps a severity onto a state Nagstamon knows

        The configured mappings are checked worst state first, so a severity listed in
        more than one of them ends up in the worse one.

        Args:
            the_severity (str): The severity that should be mapped

        Returns:
            str: The matched Nagstamon severity
        """
        for state in self.SEVERITY_MAP_OPTIONS:
            configured = getattr(self, f'map_to_{state}', '')
            if the_severity in [x.strip() for x in configured.split(',')]:
                if state == 'down':
                    # only hosts can be DOWN in Nagstamon, and an alert always becomes a
                    # service - the option is kept working for existing configurations
                    log.debug("severity '%s' is mapped to the deprecated DOWN, "
                              "treating it as CRITICAL", the_severity)
                    return "CRITICAL"
                return state.upper()

        severity = the_severity.upper()

        # a severity of 'none' means the alert is to be ignored, like the Watchdog alert
        # of a Prometheus stack
        if severity == "NONE":
            return severity

        if severity in self.SERVICE_STATES:
            return severity

        # an unmapped severity used to be handed through in upper case and was then
        # silently dropped, because get_status() only counts the states it knows -
        # see https://github.com/HenriWahl/Nagstamon/issues/797
        log.debug("severity '%s' is not mapped to any state, falling back to UNKNOWN",
                  the_severity)
        return "UNKNOWN"

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

        alert_status = alert.get("status", {})
        attempt = alert_status.get("state", "unknown")
        silenced_by = alert_status.get("silencedBy", []) or []

        if attempt == "suppressed":
            scheduled_downtime = True
            acknowledged = True
            log.debug("[%s]: detected status: '%s' -> interpreting as silenced by %s",
                      fingerprint, attempt, silenced_by)
        else:
            scheduled_downtime = False
            acknowledged = False
            log.debug("[%s]: detected status: '%s'", fingerprint, attempt)

        duration = get_duration(alert.get("startsAt"))

        annotations = alert.get("annotations", {})
        status_information = detect_from_labels(annotations,self.map_to_status_information,'')

        result['host'] = str(hostname)
        result['name'] = servicename
        result['server'] = self.name
        result['status'] = severity
        result['labels'] = labels
        result['last_check'] = get_duration(alert.get("updatedAt"))
        result['attempt'] = attempt
        result['scheduled_downtime'] = scheduled_downtime
        result['acknowledged'] = acknowledged
        result['duration'] = duration
        result['generatorURL'] = generator_url
        result['fingerprint'] = fingerprint
        result['status_information'] = status_information
        result['silenced_by'] = silenced_by

        return result


    def get_alerts_url(self):
        """Builds the URL to get the alerts from

        The configured filter may contain several matchers separated by commas, which the
        API expects as repeated filter parameters. Everything gets encoded properly - the
        filter expressions contain characters like " and = which have to be escaped.

        Returns:
            str: The URL to fetch the alerts from
        """
        parameters = [('inhibited', 'false')]
        parameters += [('filter', matcher)
                       for matcher in split_matchers(self.alertmanager_filter)]
        return f'{self.monitor_url}{self.API_PATH_ALERTS}?{urlencode(parameters)}'

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
            result = self.fetch_url(self.get_alerts_url(), giveback="raw")

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

            # anything but a list of alerts means the request did not deliver what it
            # should - iterating over it would walk the keys of an error object
            if not isinstance(data, list):
                log.error("expected a list of alerts but got '%s'", type(data).__name__)
                return Result(result=result.result,
                              error='Unexpected response from Alertmanager API',
                              status_code=status_code)

            # alerts suppressed by a silence get a second look further down
            suppressed_services = []

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
                service.silenced_by = alert_data['silenced_by']

                service.status_information = alert_data['status_information']

                if service.silenced_by:
                    suppressed_services.append(service)

                if service.host not in self.new_hosts:
                    self.new_hosts[service.host] = GenericHost()
                    self.new_hosts[service.host].name = str(service.host)
                    self.new_hosts[service.host].server = self.name
                self.new_hosts[service.host].services[service.name] = service

            self.apply_silence_kind(suppressed_services)

        except Exception as the_exception:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            log.exception(the_exception)
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def apply_silence_kind(self, services):
        """Tells acknowledgements and downtimes apart for the given silenced alerts

        Alertmanager only knows silences, so a suppressed alert used to be marked as
        acknowledged and in downtime at the same time, which makes the according filters
        useless. The comment of the silence tells which of the two it was meant to be.
        Silences created elsewhere keep counting as both.

        Args:
            services (list(AlertmanagerService)): The suppressed alerts
        """
        if not services:
            return

        silences = {silence.get('id'): silence for silence in self.get_silences()}
        if not silences:
            return

        for service in services:
            comments = [silences[silence_id].get('comment', '')
                        for silence_id in service.silenced_by
                        if silence_id in silences]
            acknowledged = any(x.startswith(self.SILENCE_COMMENT_ACKNOWLEDGE) for x in comments)
            downtime = any(x.startswith(self.SILENCE_COMMENT_DOWNTIME) for x in comments)
            # only decide if at least one silence was created by Nagstamon
            if acknowledged or downtime:
                service.acknowledged = acknowledged
                service.scheduled_downtime = downtime

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


    def get_alert(self, host, service):
        """Looks up an alert by the display name the GUI passes around

        Services are keyed by fingerprint internally, but the GUI passes display_name.

        Args:
            host (str): The host the alert belongs to
            service (str): The display name of the alert

        Returns:
            AlertmanagerService: The alert or None if it could not be found
        """
        if host not in self.hosts:
            log.error('host "%s" not found', host)
            return None
        alert = next((x for x in self.hosts[host].services.values()
                      if x.display_name == service), None)
        if alert is None:
            log.error('service "%s" not found on host "%s"', service, host)
        return alert

    def get_silence_matchers(self, alert):
        """Builds the matchers of a silence for the given alert

        Using every label of an alert makes the silence so specific that it stops matching
        as soon as one volatile label changes, so the labels to match on are configurable.
        If none of the configured labels exists on the alert all labels are used, because
        a silence without matchers would silence everything.

        Args:
            alert (AlertmanagerService): The alert to be silenced

        Returns:
            list(dict): The matchers for the silence
        """
        labels = alert.labels
        wanted = [x.strip() for x in self.silence_matcher_labels.split(',') if x.strip()]
        if wanted:
            selected = {name: value for name, value in labels.items() if name in wanted}
            if selected:
                labels = selected
            else:
                log.warning('none of the labels %s found on the alert - '
                            'falling back to all of its labels', wanted)
        return [{'name': name,
                 'value': value,
                 'isRegex': False,
                 'isEqual': True}
                for name, value in labels.items()]

    def post_silence(self, alert, author, comment, starts_at, ends_at):
        """Creates a silence for the given alert

        API Spec: https://github.com/prometheus/alertmanager/blob/master/api/v2/openapi.yaml

        Args:
            alert (AlertmanagerService): The alert to be silenced
            author (str): Who created the silence
            comment (str): Why the silence was created
            starts_at (str): Start of the silence as ISO formatted UTC time string
            ends_at (str): End of the silence as ISO formatted UTC time string

        Returns:
            Result: The result of the API call
        """
        silence_data = {'matchers': self.get_silence_matchers(alert),
                        'startsAt': starts_at,
                        'endsAt': ends_at,
                        'comment': comment,
                        'createdBy': author or 'Nagstamon'}
        log.debug('creating silence: %s', silence_data)
        # the content type is given explicitly instead of relying on the session headers
        # from init_http() - while credentials have to be renewed fetch_url() falls back
        # to a temporary session which does not carry them, and Alertmanager answers
        # anything but application/json with 415
        return self.fetch_url(self.monitor_url + self.API_PATH_SILENCES, giveback="raw",
                              cgi_data=json.dumps(silence_data),
                              headers={'Content-Type': 'application/json'})

    @staticmethod
    def build_silence_comment(marker, comment):
        """Prefixes the user comment with the marker telling what the silence stands for

        Args:
            marker (str): One of SILENCE_COMMENT_ACKNOWLEDGE or SILENCE_COMMENT_DOWNTIME
            comment (str): The comment the user entered, may be empty

        Returns:
            str: The comment to send along with the silence
        """
        if comment:
            return f'{marker}: {comment}'
        return marker

    def get_silences(self):
        """Gets all silences known to the Alertmanager

        Returns:
            list(dict): The silences, empty if they could not be retrieved
        """
        result = self.fetch_url(self.monitor_url + self.API_PATH_SILENCES, giveback="raw")
        try:
            silences = json.loads(result.result)
        except json.decoder.JSONDecodeError:
            log.error("could not decode the silences: %s", result.result)
            return []
        if not isinstance(silences, list):
            log.error("expected a list of silences but got '%s'", type(silences).__name__)
            return []
        return silences

    def expire_silence(self, silence_id):
        """Expires a single silence

        Args:
            silence_id (str): ID of the silence to expire

        Returns:
            Result: The result of the API call
        """
        log.debug("expiring silence '%s'", silence_id)
        return self.fetch_url(f'{self.monitor_url}{self.API_PATH_SILENCE}/{silence_id}',
                              giveback="raw",
                              method="DELETE")

    def remove_silences(self, host, service):
        """Expires all silences which suppress the given alert

        This is the counterpart of the acknowledgement and the downtime, both of which
        create a silence. Without it a silence could only be removed in the Alertmanager
        web interface.

        Args:
            host (str): The host the alert belongs to
            service (str): The display name of the alert

        Returns:
            int: How many silences were really expired
        """
        alert = self.get_alert(host, service)
        if alert is None:
            return 0
        if not alert.silenced_by:
            log.info('no silence to remove for "%s" on "%s"', service, host)
            return 0
        expired = 0
        for silence_id in alert.silenced_by:
            result = self.expire_silence(silence_id)
            # a failed expiration leaves the alert suppressed, so it must not be counted
            # as a success - otherwise the alert silently stays away until the next refresh
            if result.error or not 200 <= result.status_code < 300:
                log.error('could not expire silence "%s" of "%s" on "%s": %s',
                          silence_id, service, host,
                          result.error or f'status code {result.status_code}, {result.result}')
                continue
            expired += 1
        return expired

    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):

        alert = self.get_alert(host, service)
        if alert is None:
            return

        # Convert local dates to UTC
        starts_at = convert_timestring_to_utc(start_time)
        if fixed:
            ends_at = convert_timestring_to_utc(end_time)
        else:
            # a flexible downtime has no end time in the dialog, just a duration
            ends_at = add_duration_to_timestring(start_time, hours, minutes)

        self.post_silence(alert, author,
                          self.build_silence_comment(self.SILENCE_COMMENT_DOWNTIME, comment),
                          starts_at, ends_at)


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


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent,
                         all_services=None, expire_time=None):
        alert = self.get_alert(host, service)
        if alert is None:
            return

        now = datetime.now(timezone.utc)
        starts_at = now.isoformat()
        if expire_time:
            ends_at = convert_timestring_to_utc(expire_time)
        else:
            # without an end time the silence used to start and end at the very same
            # moment, which silenced exactly nothing
            ends_at = (now + timedelta(hours=self.DEFAULT_SILENCE_HOURS)).isoformat()

        comment = self.build_silence_comment(self.SILENCE_COMMENT_ACKNOWLEDGE, comment)

        self.post_silence(alert, author, comment, starts_at, ends_at)

        for service_name in all_services or []:
            service_alert = self.get_alert(host, service_name)
            if service_alert is None:
                continue
            self.post_silence(service_alert, author, comment, starts_at, ends_at)
