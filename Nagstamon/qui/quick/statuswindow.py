# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.

from os import sep

from Nagstamon.config import (AppInfo,
                              RESOURCES)
from Nagstamon.qui.qt import (QAction,
                              QIcon,
                              QMenu,
                              QObject,
                              QSystemTrayIcon,
                              QUrl,
                              Signal,
                              Slot)
from Nagstamon.servers import servers


class QuickStatusWindow(QObject):
    showing = Signal()
    hiding = Signal()
    recheck = Signal()

    def __init__(self, app, qml_engine, root, bridge):
        QObject.__init__(self)
        self.app = app
        self.engine = qml_engine
        self.root = root

        self.bridge = bridge
        self.bridge.setParent(self)

        self.bridge.recheck_requested.connect(self.recheck.emit)

        self.tray_icon = QSystemTrayIcon(QIcon(f'{RESOURCES}{sep}nagstamon.svg'), self)
        self.tray_menu = QMenu()
        self.action_show = QAction('Show', self.tray_menu)
        self.action_recheck = QAction('Recheck', self.tray_menu)
        self.action_exit = QAction('Exit', self.tray_menu)
        self.tray_menu.addAction(self.action_show)
        self.tray_menu.addAction(self.action_recheck)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.action_exit)
        self.tray_icon.setContextMenu(self.tray_menu)

        self.action_show.triggered.connect(self.show)
        self.action_recheck.triggered.connect(self.recheck.emit)
        self.action_exit.triggered.connect(self.exit)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

        self.bridge.settings_requested.connect(self._open_settings_dialog)
        self.bridge.about_requested.connect(self._open_about_dialog)
        self.bridge.version_check_requested.connect(self._open_version_check_dialog)
        self.bridge.acknowledge_requested.connect(self._open_acknowledge_dialog)
        self.bridge.downtime_requested.connect(self._open_downtime_dialog)
        self.bridge.submit_check_result_requested.connect(self._open_submit_dialog)
        self.bridge.web_login_requested.connect(self._open_weblogin_dialog)

        self.root.setTitle(AppInfo.NAME)

    def _show_dialog(self, dialog_name, *args):
        from Nagstamon.qui.dialogs import dialogs
        dialog = getattr(dialogs, dialog_name, None)
        if dialog is None:
            return
        if hasattr(dialog, 'show'):
            dialog.show(*args)

    @Slot()
    def _open_settings_dialog(self):
        self._show_dialog('settings')

    @Slot()
    def _open_about_dialog(self):
        self._show_dialog('about')

    @Slot()
    def _open_version_check_dialog(self):
        from Nagstamon.qui.dialogs.check_version import check_version
        check_version.check(start_mode=False, parent=None)

    @Slot(str)
    def _open_acknowledge_dialog(self, server_name):
        self._show_dialog('acknowledge', servers[server_name])

    @Slot(str)
    def _open_downtime_dialog(self, server_name):
        self._show_dialog('downtime', servers[server_name])

    @Slot(str)
    def _open_submit_dialog(self, server_name):
        self._show_dialog('submit', servers[server_name])

    @Slot(str)
    def _open_weblogin_dialog(self, server_name):
        self._show_dialog('weblogin', servers[server_name])

    @Slot()
    def show(self):
        self.bridge.refresh()
        self.root.show()
        self.root.raise_()
        self.showing.emit()

    @Slot()
    def hide_window(self):
        self.root.hide()
        self.hiding.emit()

    @Slot()
    def adjustSize(self):
        if hasattr(self.root, 'width') and hasattr(self.root, 'height'):
            self.root.setWidth(max(self.root.minimumWidth(), self.root.width()))
            self.root.setHeight(max(self.root.minimumHeight(), self.root.height()))

    @Slot()
    def refresh(self):
        self.bridge.refresh()

    @Slot()
    def reinitialize(self):
        self.bridge.refresh()

    @Slot()
    def exit(self):
        self.tray_icon.hide()
        self.app.quit()

    @Slot(object)
    def _on_tray_activated(self, reason):
        trigger_reason = QSystemTrayIcon.ActivationReason.Trigger \
            if hasattr(QSystemTrayIcon, 'ActivationReason') else QSystemTrayIcon.Trigger
        if reason == trigger_reason:
            if self.root.isVisible():
                self.hide_window()
            else:
                self.show()


def load_qml_engine(bridge):
    from Nagstamon.qui.qt import QT_FLAVOR

    if QT_FLAVOR == 'PyQt5':
        from PyQt5.QtQml import QQmlApplicationEngine
    else:
        from PyQt6.QtQml import QQmlApplicationEngine

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('nagstamonBridge', bridge)
    engine.load(QUrl.fromLocalFile(f'{RESOURCES}{sep}qui{sep}quick_main.qml'))

    if not engine.rootObjects():
        raise RuntimeError('QtQuick root object could not be loaded')

    return engine, engine.rootObjects()[0]
