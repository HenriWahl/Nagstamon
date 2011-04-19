# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
from Nagstamon.Server.LxmlFreeGeneric import LxmlFreeGenericServer


import urllib
import base64

class IcingaServer(LxmlFreeGenericServer):
    """
        object of Incinga server
    """   
    TYPE = 'Icinga'
    
    # needed for parsing Icinga CGI HTML
    HTML_BODY_TABLE_INDEX = 3
    
    def DISABLEDFORTESTINGget_start_end(self, host):
        """
        something changed in html layout so we need to get time somehow differently than in Nagios
        """
        result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}), giveback="raw")
        html = result.result
        start_time = html.split("NAME='start_time' VALUE='")[1].split("'")[0]
        end_time = html.split("NAME='end_time' VALUE='")[1].split("'")[0]
        # give values back as tuple
        return start_time, end_time   
    