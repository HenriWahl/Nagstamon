# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer


class NagiosServer(GenericServer):
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful   
        As Nagios is the default server type all its methods are in GenericServer
    """
    
    TYPE = 'Nagios'


    def init_config(self):
        """
        set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        #
        # the following variables are not necessary anymore as with "new" filtering
        #
        # hoststatus
        #hoststatustypes = 12
        # servicestatus
        #servicestatustypes = 253
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        #hostserviceprops = 0

        # services (unknown, warning or critical?)
        self.cgiurl_services = self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=253&serviceprops=0"
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=0"

        # SOFT/HARD states also to be checked
        # HOST_PROPERTY/SERVICE_PROPERTY 262144 = HARD state
        self.cgiurl_services_hard  = self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=253&serviceprops=262144"
        self.cgiurl_hosts_hard = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=262144"
