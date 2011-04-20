# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
#from Nagstamon.Server.LxmlFreeGeneric import LxmlFreeGenericServer


import urllib
import base64

#class IcingaServer(LxmlFreeGenericServer):
class IcingaServer(GenericServer):    
    """
        object of Incinga server
    """   
    TYPE = 'Icinga'
