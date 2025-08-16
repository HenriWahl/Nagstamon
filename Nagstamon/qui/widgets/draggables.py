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

from time import time

from Nagstamon.config import conf
from Nagstamon.qui.globals import statuswindow_properties
from Nagstamon.qui.qt import (get_global_position,
                              QLabel,
                              QSizePolicy,
                              QSvgWidget,
                              QWidget,
                              Qt,
                              Signal)


class DraggableWidget(QWidget):
    """
    used to give various top area and statusbar widgets draggability
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()
    # needed to close window in some configurations
    mouse_released_in_window = Signal()

    # keep state of right button pressed to avoid dragging and
    # unwanted repositioning of statuswindow
    right_mouse_button_pressed = False

    parent_statuswindow = None

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

    def set_menu(self, menu):
        self.menu = menu

    def mousePressEvent(self, event):
        """
        react differently to mouse button presses:
        1 - left button, move window
        2 - right button, popup menu
        """
        # update access to status window
        self.parent_statuswindow = self.parentWidget().parentWidget()
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed.emit()
        if event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_button_pressed = True

        # keep x and y relative to statusbar
        # if not set calculate relative position
        if not statuswindow_properties.relative_x and \
                not statuswindow_properties.relative_y:
            # Qt5 & Qt6 have different methods for getting the global position so take it from qt.py
            global_position = get_global_position(event)
            statuswindow_properties.relative_x = global_position.x() - self.parent_statuswindow.x()
            statuswindow_properties.relative_y = global_position.y() - self.parent_statuswindow.y()

    def mouseReleaseEvent(self, event):
        """
        decide if moving or menu should be treated after mouse button was released
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # if popup window should be closed by clicking do it now
            if statuswindow_properties.is_shown and \
                    (conf.close_details_clicking or
                     conf.close_details_clicking_somewhere) and \
                    not conf.fullscreen and not conf.windowed:
                statuswindow_properties.is_hiding_timestamp = time()
                self.mouse_released_in_window.emit()
            elif not statuswindow_properties.is_shown:
                self.mouse_released.emit()

            # reset all helper values
            statuswindow_properties.moving = False
            statuswindow_properties.relative_x = 0
            statuswindow_properties.relative_y = 0

        if event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_button_pressed = False
            self.menu.show_at_cursor()

    def mouseMoveEvent(self, event):
        """
        do the moving action
        """
        # if window should close when being clicked it might be problematic if it
        # will be moved unintendedly so try to filter this events out by waiting 0.5 seconds
        if not (conf.close_details_clicking and
                statuswindow_properties.is_shown and
                statuswindow_properties.is_shown_timestamp + 0.5 < time()):
            if not conf.fullscreen and not conf.windowed and not self.right_mouse_button_pressed:
                # Qt5 & Qt6 have different methods for getting the global position so take it from qt.py
                global_position = get_global_position(event)
                # lock window as moving
                # if not set calculate relative position
                if not statuswindow_properties.relative_x and not statuswindow_properties.relative_y:
                    statuswindow_properties.relative_x = global_position.x() - self.parent_statuswindow.x()
                    statuswindow_properties.relative_y = global_position.y() - self.parent_statuswindow.y()
                statuswindow_properties.moving = True
                # TODO: shall become a signal
                self.parent_statuswindow.move(int(global_position.x() - statuswindow_properties.relative_x),
                                                int(global_position.y() - statuswindow_properties.relative_y))

            self.window_moved.emit()

    def enterEvent(self, event):
        """
        tell the world that mouse entered the widget - interesting for hover popup and only if top area hasn't been
        clicked a moment ago
        """
        if statuswindow_properties.is_shown is False and \
                statuswindow_properties.is_hiding_timestamp + 0.2 < time():
            self.mouse_entered.emit()


class DraggableLabel(QLabel, DraggableWidget):
    """
    label with dragging capabilities used by top area
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()
    # needed to close window in some configurations
    mouse_released_in_window = Signal()

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)
