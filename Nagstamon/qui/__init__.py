# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.

from os import environ

from Nagstamon.config import conf


UI_BACKEND = str(environ.get('NAGSTAMON_UI', getattr(conf, 'ui_backend', 'classic'))).lower()

if UI_BACKEND == 'quick':
    try:
        from Nagstamon.qui.quick.bootstrap import (app,
                                                   check_version,
                                                   statuswindow)
    except Exception:
        from Nagstamon.qui.classic_bootstrap import (app,
                                                     check_version,
                                                     statuswindow)
else:
    from Nagstamon.qui.classic_bootstrap import (app,
                                                 check_version,
                                                 statuswindow)
