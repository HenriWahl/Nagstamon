# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
#from Nagstamon.Server.LxmlFreeGeneric import LxmlFreeGenericServer


class NagiosServer(GenericServer):
#class NagiosServer(LxmlFreeGenericServer):    
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful   
        As Nagios is the default server type all its methods are in GenericServer
    """
    
    TYPE = 'Nagios'
