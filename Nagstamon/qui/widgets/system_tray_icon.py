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

from os import (environ,
                sep)
from sys import stdout
from traceback import print_exc

from Nagstamon.config import (conf,
                              debug_queue,
                              OS,
                              OS_MACOS,
                              RESOURCES, OS_NON_LINUX)
from Nagstamon.qui.globals import (resource_files,
                                   status_window_properties)
from Nagstamon.qui.qt import (QCursor,
                              QMenu,
                              QPainter,
                              QPixmap,
                              QSvgRenderer,
                              QSystemTrayIcon,
                              Qt,
                              QTimer,
                              QXmlStreamReader,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.icon import QIconWithFilename
from Nagstamon.Servers import get_worst_status


class SystemTrayIcon(QSystemTrayIcon):
    """
    Icon in system tray, works at least in Windows and OSX
    Several Linux desktop environments have different problems

    For some dark, very dark reason systray menu does NOT work in
    Windows if run on commandline as nagstamon.py - the binary .exe works
    """
    show_popwin = Signal()
    hide_popwin = Signal()

    # flag for displaying error icon in case of error
    error_shown = False

    def __init__(self):
        # debug environment variables
        if conf.debug_mode:
            for environment_key, environment_value in environ.items():
                debug_queue.append(f'DEBUG: Environment variable: {environment_key}={environment_value}')

        # initialize systray icon
        QSystemTrayIcon.__init__(self)

        # icons are in dictionary
        self.icons = {}
        self.create_icons()
        # empty icon for flashing notification
        self.icons['EMPTY'] = QIconWithFilename(f'{RESOURCES}{sep}nagstamon_systrayicon_empty.svg')
        # little workaround to match statuswindow.worker_notification.worst_notification_status
        self.icons['UP'] = self.icons['OK']
        # default icon is OK
        if conf.icon_in_systray:
            self.setIcon(self.icons['OK'])

        # store icon for flashing
        self.current_icon = None

        # no menu at first
        self.menu = None

        # timer for singleshots for flashing
        self.timer = QTimer()

        # when there are new settings/colors recreate icons
        # TODO: already kicked to qui/__init__.py, check if it works
        #dialogs.settings.changed.connect(self.create_icons)

        # treat clicks
        self.activated.connect(self.icon_clicked)

    def current_icon_name(self):
        """
        internal function useful for debugging, returns the name of the
        current icon
        """
        current_account_icon = self.icon()
        if current_account_icon is None:
            return '<none>'
        return str(current_account_icon)

    @Slot(QMenu)
    def set_menu(self, menu):
        """
        create current menu for right clicks
        """
        # store menu for future use, especially for MacOSX
        self.menu = menu

        # MacOSX does not distinguish between left and right click so menu will go to upper menu bar
        # update: apparently not, but own context menu will be shown when icon is clicked an all is OK = green
        if OS != OS_MACOS:
            self.setContextMenu(self.menu)

    @Slot()
    def create_icons(self):
        """
        create icons from template, applying colors
        """
        svg_template = f'{RESOURCES}{sep}nagstamon_systrayicon_template.svg'
        # get template from file
        # by using RESOURCE_FILES the file path will be checked on macOS and the file restored if necessary
        with open(resource_files[svg_template]) as svg_template_file:
            svg_template_xml = svg_template_file.readlines()

            # create icons for all states
            for state in ['OK', 'INFORMATION', 'UNKNOWN', 'WARNING', 'AVERAGE', 'HIGH', 'CRITICAL', 'DISASTER',
                          'UNREACHABLE', 'DOWN', 'ERROR']:
                # current SVG XML for state icon, derived from svg_template_cml
                svg_state_xml = list()

                # replace dummy text and background colors with configured ones
                for line in svg_template_xml:
                    line = line.replace('fill:#ff00ff', 'fill:' + conf.__dict__['color_' + state.lower() + '_text'])
                    line = line.replace('fill:#00ff00',
                                        'fill:' + conf.__dict__['color_' + state.lower() + '_background'])
                    svg_state_xml.append(line)

                # create XML stream of SVG
                svg_xml_stream = QXmlStreamReader(''.join(svg_state_xml))
                # create renderer for SVG and put SVG XML into renderer
                svg_renderer = QSvgRenderer(svg_xml_stream)
                # pixmap to be painted on - arbitrarily choosen 128x128 px
                svg_pixmap = QPixmap(128, 128)
                # fill transparent backgound
                svg_pixmap.fill(Qt.GlobalColor.transparent)
                # initiate painter which paints onto paintdevice pixmap
                svg_painter = QPainter(svg_pixmap)
                # render svg to pixmap
                svg_renderer.render(svg_painter)
                # close painting
                svg_painter.end()
                # put pixmap into icon
                self.icons[state] = QIconWithFilename(svg_pixmap)

                debug_queue.append(f'DEBUG: SystemTrayIcon created icon {self.icons[state]} for state "{state}"')

    @Slot(QSystemTrayIcon.ActivationReason)
    def icon_clicked(self, reason):
        """
        evaluate mouse click
        """

        # retrieve icon position and store it in status_window_properties
        self.retrieve_icon_position()

        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick,
                      QSystemTrayIcon.ActivationReason.MiddleClick):
            # when green icon is displayed and no popwin is about to pop up...
            if get_worst_status() == 'UP':
                # ...nothing to do except on macOS where menu should be shown
                if OS == OS_MACOS:
                    # in case there is some error show popwin rather than context menu
                    if not self.error_shown:
                        self.menu.show_at_cursor()
                    else:
                        self.show_popwin.emit()
            else:
                # show status window if there is something to tell
                if status_window_properties.is_shown:
                    self.hide_popwin.emit()
                else:
                    self.show_popwin.emit()

    @Slot()
    def retrieve_icon_position(self):
        """
        get the coordinates of the systray icon and store it in status_window_properties
        """
        # where is the pointer which clicked onto systray icon
        icon_x = self.geometry().x()
        icon_y = self.geometry().y()
        if OS in OS_NON_LINUX:
            if status_window_properties.icon_x == 0:
                status_window_properties.icon_x = QCursor.pos().x()
            elif icon_x != 0:
                status_window_properties.icon_x = icon_x
        else:
            # strangely enough on KDE the systray icon geometry gives back 0, 0 as coordinates
            # also at Ubuntu Unity 16.04
            if icon_x == 0 and status_window_properties.icon_x == 0:
                status_window_properties.icon_x = QCursor.pos().x()
            elif icon_x != 0:
                status_window_properties.icon_x = icon_x

        if icon_y == 0 and status_window_properties.icon_y == 0:
            status_window_properties.icon_y = QCursor.pos().y()

        if OS in OS_NON_LINUX:
            if status_window_properties.icon_y == 0:
                status_window_properties.icon_y = QCursor.pos().y()
            elif icon_y != 0:
                status_window_properties.icon_y = icon_y

        pass

    @Slot()
    def show_state(self):
        """
        get the worst status and display it in systray
        """
        if not self.error_shown:
            worst_status = get_worst_status()
            self.setIcon(self.icons[worst_status])
            # set current icon for flashing
            self.current_icon = self.icons[worst_status]
            del worst_status
        else:
            self.setIcon(self.icons['ERROR'])

    @Slot()
    def flash(self):
        """
        send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if status_window_properties.is_notifying:
            # store current icon to get it reset back
            if self.current_icon is None:
                if not self.error_shown:
                    self.current_icon = self.icons[status_window_properties.worst_notification_status]
                else:
                    self.current_icon = self.icons['ERROR']
            # use empty SVG icon to display emptiness
            if resource_files[self.icons['EMPTY'].filename]:
                self.setIcon(self.icons['EMPTY'])
            # fire up a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)

    @Slot()
    def reset(self):
        """
        tell labels to set original colors
        """
        # only if currently a notification is necessary
        if status_window_properties.is_notifying:
            try:
                # set curent status icon
                self.setIcon(self.current_icon)
                # even later call itself to invert colors as flash
                self.timer.singleShot(500, self.flash)
            except:
                print_exc(file=stdout)
        else:
            if self.current_icon is not None:
                self.setIcon(self.current_icon)
            self.current_icon = None

    @Slot()
    def set_error(self):
        self.error_shown = True

    @Slot()
    def reset_error(self):
        self.error_shown = False
