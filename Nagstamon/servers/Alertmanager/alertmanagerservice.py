from Nagstamon.objects import GenericService

class AlertmanagerService(GenericService):
    """
    add alertmanager specific service property to generic service class
    """
    fingerprint = ""

    def __init__(self):
        super().__init__()
        self.labels = {}
        # IDs of the silences which suppress this alert - needed to expire them again
        self.silenced_by = []

    def get_service_name(self):
        return self.display_name

    def get_hash(self):
        """
            return hash for event history tracking
        """
        return " ".join((self.server, self.site, self.host, self.name, self.status, self.fingerprint))
