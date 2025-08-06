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
from base64 import b64encode
from os import sep

from Nagstamon.config import AppInfo, RESOURCES
from Nagstamon.qui.constants import SPACE
from Nagstamon.qui.globals import app
from Nagstamon.qui.qt import (QAction,
                              QByteArray,
                              QHBoxLayout,
                              QIcon,
                              QPainter,
                              QPixmap,
                              QPalette,
                              QSizePolicy,
                              QSvgRenderer,
                              Qt,
                              QXmlStreamReader,
                              QWidget,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.button import (Button,
                                          CSS_CLOSE_BUTTON,
                                          PushButtonHamburger)
from Nagstamon.qui.widgets.draggables import DraggableLabel
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.menu import MenuAtCursor
from Nagstamon.qui.widgets.nagstamon_logo import NagstamonLogo
from Nagstamon.qui.widgets.top_area_widgets import (ComboBoxServers)


class TopArea(QWidget):
    """
        Top area of status window
    """

    mouse_entered = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.hbox = HBoxLayout(spacing=SPACE, parent=self)  # top HBox containing buttons
        self.hbox.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMinimumSize)

        self.icons = dict()
        self.create_icons()

        # top button box
        self.logo = NagstamonLogo(self.icons['nagstamon_logo_toparea'], width=150, height=42, parent=self)
        self.label_version = DraggableLabel(text=AppInfo.VERSION, parent=self)
        self.label_empty_space = DraggableLabel(text='', parent=self)
        self.label_empty_space.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.combobox_servers = ComboBoxServers(parent=self)
        self.button_filters = Button("Filters", parent=self)
        self.button_recheck_all = Button("Recheck all", parent=self)
        self.button_refresh = Button("Refresh", parent=self)
        self.button_settings = Button("Settings", parent=self)

        # fill default order fields combobox with server names
        self.combobox_servers.fill()

        # hambuger menu
        self.button_hamburger_menu = PushButtonHamburger()
        self.button_hamburger_menu.setIcon(self.icons['menu'])
        self.hamburger_menu = MenuAtCursor()
        action_exit = QAction("Exit", self)
        # TODO: use somehow more sophisticated exit handling - shall be a signal to slot
        #       on exit() currently in qui/__init__.py
        action_exit.triggered.connect(exit)
        self.hamburger_menu.addAction(action_exit)
        self.button_hamburger_menu.setMenu(self.hamburger_menu)

        # X
        self.button_close = Button()
        self.button_close.setIcon(self.icons['close'])
        self.button_close.setStyleSheet(CSS_CLOSE_BUTTON)

        self.hbox.addWidget(self.logo)
        self.hbox.addWidget(self.label_version)
        self.hbox.addWidget(self.label_empty_space)
        self.hbox.addWidget(self.combobox_servers)
        self.hbox.addWidget(self.button_filters)
        self.hbox.addWidget(self.button_recheck_all)
        self.hbox.addWidget(self.button_refresh)
        self.hbox.addWidget(self.button_settings)
        self.hbox.addWidget(self.button_hamburger_menu)
        self.hbox.addWidget(self.button_close)

        self.setLayout(self.hbox)

    def enterEvent(self, event):
        # unlock statuswindow if pointer touches statusbar
        self.mouse_entered.emit()

    @Slot()
    def create_icons(self):
        """
        create icons from template, applying colors
        """
        # get rgb values of current foreground color to be used for SVG icons (menu)
        r, g, b, a = app.palette().color(QPalette.ColorRole.Text).getRgb()

        for icon in 'nagstamon_logo_toparea', 'close', 'menu':
            # get template from file
            svg_template_file = open(f'{RESOURCES}{sep}{icon}_template.svg')
            svg_template_xml = svg_template_file.readlines()

            # current SVG XML for state icon, derived from svg_template_cml
            svg_icon_xml = list()

            # replace dummy text and background colors with configured ones
            for line in svg_template_xml:
                line = line.replace('fill:#ff00ff', 'fill:#{0:x}{1:x}{2:x}'.format(r, g, b))
                svg_icon_xml.append(line)

            # create XML stream of SVG
            svg_xml_stream = QXmlStreamReader(''.join(svg_icon_xml))

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

            # two ways...
            if icon == 'nagstamon_logo_toparea':
                # first get a base64 version of the SVG
                svg_base64 = b64encode(bytes(''.join(svg_icon_xml), 'utf8'))
                # create a QByteArray for NagstamonLogo aka QSvgWidget
                svg_bytes = QByteArray.fromBase64(svg_base64)
                self.icons[icon] = svg_bytes
            else:
                # put pixmap into icon
                self.icons[icon] = QIcon(svg_pixmap)
