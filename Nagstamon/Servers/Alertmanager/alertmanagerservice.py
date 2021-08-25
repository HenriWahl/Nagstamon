from Nagstamon.Objects import GenericService

class AlertmanagerService(GenericService):
    """
    add alertmanager specific service property to generic service class
    """
    service_object_id = ""
    labels = {}