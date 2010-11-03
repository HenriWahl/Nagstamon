# encoding: utf-8

import urllib
import urllib2
import cookielib
import sys
import socket
import gc
import copy
import webbrowser
import urllib
import time

try:
    import lxml.etree, lxml.objectify
except Exception, err:
    print
    print err
    print
    print "Could not load lxml.etree, lxml.objectify and lxml.html.clean, maybe you need to install python lxml."
    print
    sys.exit()
# fedora 8 and maybe others use lxml 2 which is more careful and offers more modules
# but which also makes necessary to clean Nagios html output
# if not available should be ok because not needed
try:
    import lxml.html.clean
except:
    pass
    
import nagstamonActions


class Column(object):
    ATTR_NAME = 'name'
    LABEL = 'Name'
    DEFAULT_VALUE = ''
    SORT_FUNCTION_NAME = 'sort_function'
    
    def __init__(self, row):
        self.value = self._get_value(row)
    
    def __str__(self):
        return str(self.value)

    def _get_value(self, row):
        if hasattr(row, self.ATTR_NAME):
            return getattr(row, self.ATTR_NAME)
        return self.DEFAULT_VALUE 
   
    @classmethod
    def get_label(cls):
        """ Table header column label
        """
        return ' '.join([x.capitalize() for x in cls.ATTR_NAME.split('_')])
   
    @classmethod
    def has_customized_sorting(cls):
        return hasattr(cls, cls.SORT_FUNCTION_NAME)
    
class CustomSortingColumn(Column):
    CHOICES = [] # list of expcted values with expected order
    
    @classmethod
    def sort_function(cls, model, iter1, iter2, column):
        """ Overrides default sorting behaviour """
        data1, data2 = [model.get_value(x, column) for x in (iter1, iter2)]
        try:
            first = cls.CHOICES.index(data1) 
            second = cls.CHOICES.index(data2)
        except ValueError: # value not in CHOICES
            return cmp(first, second)
        return first - second
    
class StatusColumn(CustomSortingColumn):
    ATTR_NAME = 'status'
    CHOICES = ['DOWN', 'UNREACHABLE', 'CRITICAL', 'UNKNOWN', 'WARNING']

class HostColumn(Column):
    ATTR_NAME = 'host'
    
    def _get_value(self, row):
       return row.get_host_name() 
 
class ServiceColumn(Column):
    def _get_value(self, row):
        return row.get_service_name()
    
    @classmethod
    def get_label(cls):
        return 'Service'
    
class LastCheckColumn(Column):
    ATTR_NAME = 'last_check'
    
class DurationColumn(CustomSortingColumn):
    ATTR_NAME = 'duration'
    
    @classmethod
    def sort_function(cls, model, iter1, iter2, column):
        """ Overrides default sorting behaviour """       
        data1, data2 = [model.get_value(x, column) for x in (iter1, iter2)]
        try:
            first = nagstamonActions.MachineSortableDuration(data1) 
            second = nagstamonActions.MachineSortableDuration(data2)
        except ValueError:
            return cmp(first, second)
        return first - second

    
class AttemptColumn(Column):
    ATTR_NAME = 'attempt'
    
class StatusInformationColumn(Column):
    ATTR_NAME = 'status_information'

class GenericObject(object):    
    def get_host_name(self):
        """ Extracts host name from status item.
        Presentation purpose.
        """
        return ''
    
    def get_service_name(self):
        """ Extracts service name from status item.
        Presentation purpose.
        """
        return ''
    
class GenericHost(GenericObject):
    """
        one host which is monitored by a Nagios server, gets populated with services
    """
    def __init__(self):
        self.name = ""
        self.status = ""
        self.last_check = ""
        self.duration = ""
        self.attempt = ""
        self.status_information = ""
        self.services = dict()
        
    def get_host_name(self):
        return self.name

    
class GenericService(GenericObject):
    """
        one service which runs on a host
    """
    def __init__(self):
        self.name = ""
        self.host = ""
        self.status = ""
        self.last_check = ""
        self.duration = ""
        self.attempt = ""
        self.status_information = ""
        
    def get_host_name(self):
        return self.host
    
    def get_service_name(self):
        return self.name 
    

class FetchURLResult(object):
    """
    a given back object might be easier enriched with ERROR information than a string or worse, a list
    """
    result = ""
    is_failed = False
    error_message = ""
    
    def __init__(self, **kwds):
        print kwds

