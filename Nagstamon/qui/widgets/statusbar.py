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

from os import sep

from collections import OrderedDict

from Nagstamon.config import (conf,
                              RESOURCES)
from Nagstamon.qui.constants import (COLORS,
                                     COLOR_STATE_NAMES)
from Nagstamon.qui.globals import statuswindow_properties, font
from Nagstamon.qui.qt import (QSizePolicy,
                              QTimer,
                              QWidget,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.draggables import DraggableLabel
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.nagstamon_logo import NagstamonLogo
from Nagstamon.servers import servers, get_errors


class StatusBarLabel(DraggableLabel):
    """
    one piece of the status bar labels for one state
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

    def __init__(self, state, parent=None):
        DraggableLabel.__init__(self, parent=parent)
        self.setStyleSheet(f'''padding-left: 1px;
                               padding-right: 1px;
                               color: {conf.__dict__[f'color_{state.lower()}_text']};
                               background-color: {conf.__dict__[f'color_{state.lower()}_background']};
                            ''')
        # just let labels grow as much as they need
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # hidden per default
        self.hide()

        # default text - only useful in case of OK Label
        self.setText(state)

        # number of hosts/services of this state
        self.number = 0

        # store state of label to access long state names in .summarize_states()
        self.state = state

    @Slot()
    def invert(self):
        self.setStyleSheet(f'''padding-left: 1px;
                               padding-right: 1px;
                               color: {conf.__dict__[f'color_{self.state.lower()}_background']};
                               background-color: {conf.__dict__[f'color_{self.state.lower()}_text']};
                            ''')

    @Slot()
    def reset(self):
        self.setStyleSheet(f'''padding-left: 1px;
                               padding-right: 1px;
                               color: {conf.__dict__[f'color_{self.state.lower()}_text']};
                               background-color: {conf.__dict__[f'color_{self.state.lower()}_background']};
                            ''')


class StatusBar(QWidget):
    """
    status bar for short display of problems
    """

    # send signal to statuswindow
    resize = Signal()

    # needed to maintain flashing labels
    labels_invert = Signal()
    labels_reset = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.hbox = HBoxLayout(spacing=0, parent=parent)
        self.setLayout(self.hbox)

        # define labels first to get their size for svg logo dimensions
        self.color_labels = OrderedDict()
        self.color_labels['OK'] = StatusBarLabel('OK', parent=parent)

        for state in COLORS:
            self.color_labels[state] = StatusBarLabel(state, parent=parent)
            self.labels_invert.connect(self.color_labels[state].invert)
            self.labels_reset.connect(self.color_labels[state].reset)

        # label for error message(s)
        self.label_message = StatusBarLabel('error', parent=parent)
        self.labels_invert.connect(self.label_message.invert)
        self.labels_reset.connect(self.label_message.reset)

        # derive logo dimensions from status label
        self.logo = NagstamonLogo('{0}{1}nagstamon_logo_bar.svg'.format(RESOURCES, sep),
                                  self.color_labels['OK'].fontMetrics().height(),
                                  self.color_labels['OK'].fontMetrics().height(),
                                  parent=parent)

        # add logo
        self.hbox.addWidget(self.logo)

        # label for error messages
        self.hbox.addWidget(self.label_message)
        self.label_message.hide()

        # add state labels
        self.hbox.addWidget(self.color_labels['OK'])
        for state in COLORS:
            self.hbox.addWidget(self.color_labels[state])

        # timer for singleshots for flashing
        self.timer = QTimer()

        self.adjust_size()

    @Slot()
    def summarize_states(self):
        """
        display summaries of states in statusbar
        """
        # initial zeros
        for label in self.color_labels.values():
            label.number = 0

        # only count numbers of enabled monitor servers
        for server in (filter(lambda s: s.enabled, servers.values())):
            for state in COLORS:
                self.color_labels[state].number += server.__dict__[state.lower()]

        # summarize all numbers - if all_numbers keeps 0 everything seems to be OK
        all_numbers = 0

        # repaint colored labels or hide them if necessary
        for label in self.color_labels.values():
            if label.number == 0:
                label.hide()
            else:
                label.setText(' '.join((str(label.number),
                                        COLOR_STATE_NAMES[label.state][conf.long_display])))
                label.show()
                label.adjustSize()
                all_numbers += label.number

        if all_numbers == 0 and not get_errors() and not self.label_message.isVisible():
            self.color_labels['OK'].show()
            self.color_labels['OK'].adjustSize()
        else:
            self.color_labels['OK'].hide()

        # fix size after refresh - better done here to avoid ugly artefacts
        hint = self.sizeHint()
        self.setMaximumSize(hint)
        self.setMinimumSize(hint)
        del hint
        # tell statuswindow its size might be adjusted
        self.resize.emit()

    @Slot()
    def flash(self):
        """
        send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if statuswindow_properties.is_notifying:
            self.labels_invert.emit()
            # fire up  a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)

    @Slot()
    def reset(self):
        """
        tell labels to set original colors
        """
        self.labels_reset.emit()
        # only if currently a notification is necessary
        if statuswindow_properties.is_notifying:
            # even later call itself to invert colors as flash
            self.timer.singleShot(500, self.flash)

    @Slot()
    def adjust_size(self):
        """
        apply new size of widgets, especially Nagstamon logo
        run through all labels to the the max height in case not all labels
        are shown at the same time - which is very likely the case
        """
        # take height for logo
        # height = 0

        # run through labels to set font and get height for logo
        for label in self.color_labels.values():
            label.setFont(font)
        #    if label.fontMetrics().height() > height:
        #        height = label.fontMetrics().height()

        self.label_message.setFont(font)
        height = self.label_message.sizeHint().height()

        # adjust logo size to fit to label size - due to being a square height and width are the same
        self.logo.adjust_size(height, height)

        # avoid flickering/artefact by updating immediately
        self.summarize_states()

    @Slot(str)
    def set_error(self, message):
        """
        display error message if any error exists
        """
        self.label_message.setText(message)
        self.label_message.show()

    @Slot()
    def reset_error(self):
        """
        delete error message if there is no error
        """
        if not get_errors():
            self.label_message.setText('')
            self.label_message.hide()
