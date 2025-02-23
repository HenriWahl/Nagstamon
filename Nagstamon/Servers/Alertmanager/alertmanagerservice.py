from Nagstamon.Objects import GenericService

class AlertmanagerService(GenericService):
    """
    add alertmanager specific service property to generic service class
    """
    fingerprint = ""
    labels = {}

    def get_service_name(self):
        return self.display_name

    def get_hash(self):
        """
            return hash for event history tracking
        """
        return " ".join((self.server, self.site, self.host, self.name, self.status, self.fingerprint))
