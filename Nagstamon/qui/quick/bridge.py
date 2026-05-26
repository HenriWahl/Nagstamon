# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.

from Nagstamon.config import conf
from Nagstamon.qui.qt import (QObject,
                              QT_FLAVOR,
                              QTimer,
                              Signal,
                              Slot)
from Nagstamon.servers import (get_status_count,
                               servers)

if QT_FLAVOR == 'PyQt5':
    from PyQt5.QtCore import pyqtProperty as Property
else:
    from PyQt6.QtCore import pyqtProperty as Property


class QuickBridge(QObject):
    counts_changed = Signal()
    servers_changed = Signal()
    selected_server_changed = Signal()

    recheck_requested = Signal()
    settings_requested = Signal()
    about_requested = Signal()
    acknowledge_requested = Signal(str)
    downtime_requested = Signal(str)
    submit_check_result_requested = Signal(str)
    web_login_requested = Signal(str)
    version_check_requested = Signal()

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._counts = {}
        self._server_names = []
        self._selected_server = ''

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1000, int(conf.update_interval_seconds) * 1000))

        self.refresh()

    @Property(int, notify=counts_changed)
    def unknownCount(self):
        return self._counts.get('UNKNOWN', 0)

    @Property(int, notify=counts_changed)
    def warningCount(self):
        return self._counts.get('WARNING', 0)

    @Property(int, notify=counts_changed)
    def criticalCount(self):
        return self._counts.get('CRITICAL', 0)

    @Property(int, notify=counts_changed)
    def downCount(self):
        return self._counts.get('DOWN', 0)

    @Property(int, notify=counts_changed)
    def unreachableCount(self):
        return self._counts.get('UNREACHABLE', 0)

    @Property('QVariantList', notify=servers_changed)
    def serverNames(self):
        return self._server_names

    @Property(str, notify=selected_server_changed)
    def selectedServer(self):
        return self._selected_server

    @Slot(str)
    def select_server(self, server_name):
        if server_name != self._selected_server:
            self._selected_server = server_name
            self.selected_server_changed.emit()

    @Slot()
    def refresh(self):
        self._counts = get_status_count()
        server_names = [name for name in servers.keys() if conf.servers[name].enabled is True]
        if server_names != self._server_names:
            self._server_names = server_names
            self.servers_changed.emit()
            if self._selected_server not in self._server_names:
                self._selected_server = self._server_names[0] if self._server_names else ''
                self.selected_server_changed.emit()
        self.counts_changed.emit()

    @Slot()
    def trigger_recheck(self):
        self.recheck_requested.emit()

    @Slot()
    def open_settings(self):
        self.settings_requested.emit()

    @Slot()
    def open_about(self):
        self.about_requested.emit()

    @Slot()
    def check_version(self):
        self.version_check_requested.emit()

    @Slot()
    def acknowledge(self):
        if self._selected_server:
            self.acknowledge_requested.emit(self._selected_server)

    @Slot()
    def downtime(self):
        if self._selected_server:
            self.downtime_requested.emit(self._selected_server)

    @Slot()
    def submit_check_result(self):
        if self._selected_server:
            self.submit_check_result_requested.emit(self._selected_server)

    @Slot()
    def web_login(self):
        if self._selected_server:
            self.web_login_requested.emit(self._selected_server)
