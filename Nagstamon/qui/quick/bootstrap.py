# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.

from Nagstamon.qui.widgets.app import app
from Nagstamon.qui.dialogs.check_version import check_version
from Nagstamon.qui.quick.bridge import QuickBridge
from Nagstamon.qui.quick.statuswindow import (QuickStatusWindow,
                                              load_qml_engine)


bridge = QuickBridge()
engine, root = load_qml_engine(bridge)
statuswindow = QuickStatusWindow(app=app,
                                 qml_engine=engine,
                                 root=root,
                                 bridge=bridge)

check_version.version_info_retrieved.connect(statuswindow.hide_window)
statuswindow.recheck.connect(statuswindow.bridge.refresh)
