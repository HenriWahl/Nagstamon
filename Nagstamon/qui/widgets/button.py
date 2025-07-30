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
