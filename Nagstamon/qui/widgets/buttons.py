# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

from Nagstamon.qui.qt import (QMenu,
                              QPushButton,
                              QToolButton,
                              Signal,
                              Slot)

from Nagstamon.config import (OS,
                              OS_MACOS)


class FlatButton(QToolButton):
    """
    A QToolButton that visually and functionally acts as a push button.

    Args:
        text (str, optional): The button label text. Defaults to an empty string.
        parent (QWidget, optional): The parent widget. Defaults to None.
        server (optional): Optional server reference for context. Defaults to None.
        url_type (str, optional): Optional URL type for button context. Defaults to an empty string.

    Attributes:
        Inherits all attributes from QToolButton.
    """

    def __init__(self, text='', parent=None, server=None, url_type=''):
        QToolButton.__init__(self, parent=parent)
        self.setAutoRaise(True)
        self.setStyleSheet('''padding: 3px;''')
        self.setText(text)


# OSX does not support flat QToolButtons so keep the neat default ones
if OS == OS_MACOS:
    Button = QPushButton
    CSS_CLOSE_BUTTON = '''QPushButton {border-width: 0px;
                                       border-style: none;
                                       margin-right: 5px;}
                          QPushButton:hover {background-color: white;
                                             border-radius: 4px;}'''
    CSS_HAMBURGER_MENU = '''QPushButton {border-width: 0px;
                                         border-style: none;}
                            QPushButton::menu-indicator{image:url(none.jpg)};
                            QPushButton:hover {background-color: white;
                                               border-radius: 4px;}'''
else:
    Button = FlatButton
    CSS_CLOSE_BUTTON = '''margin-right: 5px;'''
    CSS_HAMBURGER_MENU = '''FlatButton::menu-indicator{image:url(none.jpg);}'''


class PushButtonHamburger(Button):
    """
    A push button styled as a hamburger menu button with an attached menu.

    Attributes:
        pressed (Signal): Emitted when the button is pressed.

    Methods:
        mousePressEvent(event): Emits the `pressed` signal and shows the menu.
        set_menu(menu): Sets the menu to be displayed when the button is pressed.

    Usage:
        Use this button to provide a compact menu access point, typically represented
        by a hamburger icon, in toolbars or application headers.
    """

    pressed = Signal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(CSS_HAMBURGER_MENU)

    def mousePressEvent(self, event):
        self.pressed.emit()
        self.showMenu()

    @Slot(QMenu)
    def set_menu(self, menu):
        self.setMenu(menu)


class PushButtonBrowserURL(Button):
    """
    QPushButton for ServerVBox which opens certain URL if clicked
    """

    def __init__(self, text='', parent=None, server=None, url_type=''):
        Button.__init__(self, text, parent=parent)
        self.server = server
        self.url_type = url_type
        self.status_window = self.parentWidget().parentWidget()

    @Slot()
    def open_url(self):
        """
        open URL from BROWSER_URLS in webbrowser
        """
        # BROWSER_URLS come with $MONITOR$ instead of real monitor url - heritage from actions
        url = self.server.BROWSER_URLS[self.url_type]
        url = url.replace('$MONITOR$', self.server.monitor_url)
        url = url.replace('$MONITOR-CGI$', self.server.monitor_cgi_url)

        if conf.debug_mode:
            self.server.debug(server=self.server.get_name(), debug='Open {0} web page {1}'.format(self.url_type, url))

        # use Python method to open browser
        webbrowser_open(url)

        # hide status window to get screen space for browser
        if not conf.fullscreen and not conf.windowed:
            # TODO: shall become a signal
            self.status_window.hide_window()