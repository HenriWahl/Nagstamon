# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
from Nagstamon.Server.LxmlFreeGeneric import LxmlFreeGenericServer

import base64


#class NagiosServer(GenericServer):
class NagiosServer(LxmlFreeGenericServer):    
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful   
        As Nagios is the default server type all its methods are in GenericServer
    """
    
    TYPE = 'Nagios'
    
    # used in Nagios + Icinga _get_status() method
    HTML_BODY_TABLE_INDEX = 2
    
    # used for LxmlFreeGenericServer/BeautifulSoup
    STATUS_CLASS = 'status'
        
