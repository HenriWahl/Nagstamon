# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
import urllib


class IcingaServer(GenericServer):    
    """
        object of Incinga server
    """   
    TYPE = 'Icinga'

    
    # the following makes the situation more confusing.... Icinga seems to include that
    # strange Nagios bug regarding acknowledgement flags but behaves even more inconsistent...
    # in contrast to Nagios where absense of flags means that they are switched of here
    # stuff only happens if they are set...
    
    """
    # Nagios CGI flags translation dictionary for acknowledging hosts/services 
    HTML_ACKFLAGS = {True:"on", False:"off"}

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        url = self.nagios_cgi_url + "/cmd.cgi"      
        
        # decision about host or service - they have different URLs
        # do not care about the doube %s (%s%s) - its ok, "flags" cares about the necessary "&"
        if service == "":
            # host
            cgi_data = urllib.urlencode({"cmd_typ":"33", "cmd_mod":"2", "host":host, "com_author":author,\
                                         "sticky_ack":self.HTML_ACKFLAGS[sticky], "send_notification":self.HTML_ACKFLAGS[notify], "persistent":self.HTML_ACKFLAGS[persistent],\
                                         "com_data":comment, "btnSubmit":"Commit"})
            self.FetchURL(url, giveback="raw", cgi_data=cgi_data) 
            
        # if host is acknowledged and all services should be to or if a service is acknowledged
        # (and all other on this host too)
        if service != "":
            # service @ host
            cgi_data = urllib.urlencode({"cmd_typ":"34", "cmd_mod":"2", "host":host, "service":service,\
                                         "sticky_ack":self.HTML_ACKFLAGS[sticky], "send_notification":self.HTML_ACKFLAGS[notify], "persistent":self.HTML_ACKFLAGS[persistent],\
                                         "com_author":author, "com_data":comment, "btnSubmit":"Commit"})          
            # running remote cgi command        
            self.FetchURL(url, giveback="raw", cgi_data=cgi_data) 

        # acknowledge all services on a host
        if len(all_services) > 0:
            for s in all_services:
                # service @ host
                cgi_data = urllib.urlencode({"cmd_typ":"34", "cmd_mod":"2", "host":host, "service":s,\
                                             "sticky_ack":self.HTML_ACKFLAGS[sticky], "send_notification":self.HTML_ACKFLAGS[notify], "persistent":self.HTML_ACKFLAGS[persistent],\
                                             "com_author":author, "com_data":comment, "btnSubmit":"Commit"})
                #running remote cgi command        
                self.FetchURL(url, giveback="raw", cgi_data=cgi_data)
    """