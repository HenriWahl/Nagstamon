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

from Nagstamon.Config import (AppInfo,
                              OS,
                              OS_NON_LINUX,
                              OS_MACOS)
from Nagstamon.qui.qt import (Signal,
                              Slot,
                              QWidget)

from Nagstamon.qui.widgets.dialogs.check_version import check_version
from Nagstamon.qui.widgets.dialogs.dialog import Dialog


class DialogSettings(Dialog):
    """
        class for settings dialog
    """

    # signal to be fired if OK button was clicked and new setting are applied
    changed = Signal()

    # send signal if check for new version is wanted
    check_for_new_version = Signal(bool, QWidget)

    # used to tell debug loop it should start
    start_debug_loop = Signal()

    def __init__(self):
        Dialog.__init__(self, 'settings_main')
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
            # debug mode
            self.window.input_checkbox_debug_mode: [self.window.input_checkbox_debug_to_file,
                                                    self.window.input_lineedit_debug_file],
            # regular expressions for filtering hosts
            self.window.input_checkbox_re_host_enabled: [self.window.input_lineedit_re_host_pattern,
                                                         self.window.input_checkbox_re_host_reverse],
            # regular expressions for filtering services
            self.window.input_checkbox_re_service_enabled: [self.window.input_lineedit_re_service_pattern,
                                                            self.window.input_checkbox_re_service_reverse],
            # regular expressions for filtering status information
            self.window.input_checkbox_re_status_information_enabled: [
                self.window.input_lineedit_re_status_information_pattern,
                self.window.input_checkbox_re_status_information_reverse],
            # regular expressions for filtering duration
            self.window.input_checkbox_re_duration_enabled: [self.window.input_lineedit_re_duration_pattern,
                                                             self.window.input_checkbox_re_duration_reverse],
            # regular expressions for filtering duration
            self.window.input_checkbox_re_attempt_enabled: [self.window.input_lineedit_re_attempt_pattern,
                                                            self.window.input_checkbox_re_attempt_reverse],
            # regular expressions for filtering groups
            self.window.input_checkbox_re_groups_enabled: [self.window.input_lineedit_re_groups_pattern,
                                                           self.window.input_checkbox_re_groups_reverse],
            # offset for statuswindow when using systray
            self.window.input_radiobutton_icon_in_systray: [self.window.input_checkbox_systray_offset_use],
            self.window.input_checkbox_systray_offset_use: [self.window.input_spinbox_systray_offset,
                                                            self.window.label_offset_statuswindow],
            # display to use in fullscreen mode
            self.window.input_radiobutton_fullscreen: [self.window.label_fullscreen_display,
                                                       self.window.input_combobox_fullscreen_display],
            # notifications in general
            self.window.input_checkbox_notification: [self.window.notification_groupbox],
            # sound at all
            self.window.input_checkbox_notification_sound: [self.window.notification_sounds_groupbox],
            # custom sounds
            self.window.input_radiobutton_notification_custom_sound: [self.window.notification_custom_sounds_groupbox],
            # notification actions
            self.window.input_checkbox_notification_actions: [self.window.notification_actions_groupbox],
            # several notification actions depending on status
            self.window.input_checkbox_notification_action_warning: [
                self.window.input_lineedit_notification_action_warning_string],
            self.window.input_checkbox_notification_action_critical: [
                self.window.input_lineedit_notification_action_critical_string],
            self.window.input_checkbox_notification_action_down: [
                self.window.input_lineedit_notification_action_down_string],
            self.window.input_checkbox_notification_action_ok: [
                self.window.input_lineedit_notification_action_ok_string],
            # single custom notification action
            self.window.input_checkbox_notification_custom_action: [self.window.notification_custom_action_groupbox],
            # use event separator or not
            self.window.input_checkbox_notification_custom_action_single: [
                self.window.label_notification_custom_action_separator,
                self.window.input_lineedit_notification_custom_action_separator],
            # customized color alternation
            self.window.input_checkbox_show_grid: [self.window.input_checkbox_grid_use_custom_intensity],
            self.window.input_checkbox_grid_use_custom_intensity: [self.window.input_slider_grid_alternation_intensity,
                                                                   self.window.label_intensity_information_0,
                                                                   self.window.label_intensity_information_1,
                                                                   self.window.label_intensity_warning_0,
                                                                   self.window.label_intensity_warning_1,
                                                                   self.window.label_intensity_average_0,
                                                                   self.window.label_intensity_average_1,
                                                                   self.window.label_intensity_high_0,
                                                                   self.window.label_intensity_high_1,
                                                                   self.window.label_intensity_critical_0,
                                                                   self.window.label_intensity_critical_1,
                                                                   self.window.label_intensity_disaster_0,
                                                                   self.window.label_intensity_disaster_1,
                                                                   self.window.label_intensity_down_0,
                                                                   self.window.label_intensity_down_1,
                                                                   self.window.label_intensity_unreachable_0,
                                                                   self.window.label_intensity_unreachable_1,
                                                                   self.window.label_intensity_unknown_0,
                                                                   self.window.label_intensity_unknown_1],
            self.window.input_radiobutton_use_custom_browser: [self.window.groupbox_custom_browser,
                                                               self.window.input_lineedit_custom_browser,
                                                               self.window.button_choose_browser]}

        self.TOGGLE_DEPS_INVERTED = [self.window.input_checkbox_notification_custom_action_single]

        # because this makes only sense in macOS these dependencies will be added here
        if OS == OS_MACOS:
            # offer option to hide icon in dock on macOS
            self.TOGGLE_DEPS.update({
                self.window.input_radiobutton_icon_in_systray: [self.window.input_checkbox_hide_macos_dock_icon]})

        # show option to enable position fix only on Unices
        if not OS in OS_NON_LINUX:
            self.window.input_checkbox_enable_position_fix.show()
        else:
            self.window.input_checkbox_enable_position_fix.hide()

        # set title to current version
        self.window.setWindowTitle(' '.join((AppInfo.NAME, AppInfo.VERSION)))

        # connect server buttons to server dialog
        self.window.button_new_server.clicked.connect(self.new_server)
        self.window.button_edit_server.clicked.connect(self.edit_server)
        self.window.button_copy_server.clicked.connect(self.copy_server)
        self.window.button_delete_server.clicked.connect(self.delete_server)

        # double click on server to edit
        self.window.list_servers.doubleClicked.connect(self.edit_server)

        # connect check-for-updates button to update check
        # self.window.button_check_for_new_version_now.clicked.connect(check_version.check)
        self.window.button_check_for_new_version_now.clicked.connect(self.button_check_for_new_version_clicked)
        self.check_for_new_version.connect(check_version.check)

        # avoid offset spinbox if offset is not enabled
        self.window.input_radiobutton_windowed.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_fullscreen.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_icon_in_systray.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_statusbar_floating.clicked.connect(self.toggle_systray_icon_offset)

        # connect font chooser button to font choosing dialog
        self.window.button_fontchooser.clicked.connect(self.font_chooser)
        # connect revert-to-default-font button
        self.window.button_default_font.clicked.connect(self.font_default)
        # store font as default
        self.font = FONT
        # show current font in label_font
        self.window.label_font.setFont(FONT)

        # connect action buttons to action dialog
        self.window.button_new_action.clicked.connect(self.new_action)
        self.window.button_edit_action.clicked.connect(self.edit_action)
        self.window.button_copy_action.clicked.connect(self.copy_action)
        self.window.button_delete_action.clicked.connect(self.delete_action)

        # double click on action to edit
        self.window.list_actions.doubleClicked.connect(self.edit_action)

        # connect custom sound file buttons
        self.window.button_choose_warning.clicked.connect(self.choose_sound_file_warning)
        self.window.button_choose_critical.clicked.connect(self.choose_sound_file_critical)
        self.window.button_choose_down.clicked.connect(self.choose_sound_file_down)

        # connect custom sound file buttons
        self.window.button_play_warning.clicked.connect(self.play_sound_file_warning)
        self.window.button_play_critical.clicked.connect(self.play_sound_file_critical)
        self.window.button_play_down.clicked.connect(self.play_sound_file_down)

        # only show desktop notification on systems that support it
        if not dbus_connection.connected:
            self.window.input_checkbox_notification_desktop.hide()

        # set folder and play symbols to choose and play buttons
        self.window.button_choose_warning.setText('')
        self.window.button_choose_warning.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_warning.setText('')
        self.window.button_play_warning.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.window.button_choose_critical.setText('')
        self.window.button_choose_critical.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_critical.setText('')
        self.window.button_play_critical.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.window.button_choose_down.setText('')
        self.window.button_choose_down.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_down.setText('')
        self.window.button_play_down.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        # set browser file chooser icon and current custom browser path
        self.window.button_choose_browser.setText('')
        self.window.button_choose_browser.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.input_lineedit_custom_browser.setText(conf.custom_browser)
        # connect choose browser button with file dialog
        self.window.button_choose_browser.clicked.connect(self.choose_browser_executable)

        # QSignalMapper needed to connect all color buttons to color dialogs
        self.signalmapper_colors = QSignalMapper()

        # connect color buttons with color dialog
        for widget in [x for x in self.window.__dict__ if x.startswith('input_button_color_')]:
            button = self.window.__dict__[widget]
            item = widget.split('input_button_color_')[1]
            # multiplex slot for open color dialog by signal-mapping
            self.signalmapper_colors.setMapping(button, item)
            button.clicked.connect(self.signalmapper_colors.map)

        # connect reset and defaults buttons
        self.window.button_colors_reset.clicked.connect(self.paint_colors)
        self.window.button_colors_reset.clicked.connect(self.paint_color_alternation)
        self.window.button_colors_reset.clicked.connect(self.change_color_alternation_by_value)
        self.window.button_colors_defaults.clicked.connect(self.colors_defaults)
        self.window.button_colors_defaults.clicked.connect(self.paint_color_alternation)
        self.window.button_colors_defaults.clicked.connect(self.change_color_alternation_by_value)

        # paint alternating colors when example is wanted for customized intensity
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.paint_color_alternation)
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.change_color_alternation_by_value)
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.toggle_zabbix_widgets)

        # finally map signals with .sender() - [<type>] is important!
        self.signalmapper_colors.mappedString[str].connect(self.color_chooser)

        # connect slider to alternating colors
        self.window.input_slider_grid_alternation_intensity.valueChanged.connect(self.change_color_alternation)

        # apply toggle-dependencies between checkboxes and certain widgets
        self.toggle_toggles()

        # workaround to avoid gigantic settings dialog
        # list of Zabbix-related widgets, only to be shown if there is a Zabbix monitor server configured
        self.ZABBIX_WIDGETS = [self.window.input_checkbox_filter_all_average_services,
                               self.window.input_checkbox_filter_all_disaster_services,
                               self.window.input_checkbox_filter_all_high_services,
                               self.window.input_checkbox_filter_all_information_services,
                               self.window.input_checkbox_notify_if_average,
                               self.window.input_checkbox_notify_if_disaster,
                               self.window.input_checkbox_notify_if_high,
                               self.window.input_checkbox_notify_if_information,
                               self.window.input_button_color_average_text,
                               self.window.input_button_color_average_background,
                               self.window.input_button_color_disaster_text,
                               self.window.input_button_color_disaster_background,
                               self.window.input_button_color_high_text,
                               self.window.input_button_color_high_background,
                               self.window.input_button_color_information_text,
                               self.window.input_button_color_information_background,
                               self.window.label_color_average,
                               self.window.label_color_disaster,
                               self.window.label_color_high,
                               self.window.label_color_information]

        # Labes for customized color intensity
        self.ZABBIX_COLOR_INTENSITY_LABELS = [self.window.label_intensity_average_0,
                                              self.window.label_intensity_average_1,
                                              self.window.label_intensity_disaster_0,
                                              self.window.label_intensity_disaster_1,
                                              self.window.label_intensity_high_0,
                                              self.window.label_intensity_high_1,
                                              self.window.label_intensity_information_0,
                                              self.window.label_intensity_information_1]

        # the next workaround...
        self.OP5MONITOR_WIDGETS = [self.window.input_checkbox_re_groups_enabled,
                                   self.window.input_lineedit_re_groups_pattern,
                                   self.window.input_checkbox_re_groups_reverse]

        # ...and another...
        self.EXPIRE_TIME_WIDGETS = [self.window.input_checkbox_defaults_acknowledge_expire,
                                    self.window.label_expire_in,
                                    self.window.label_expire_in_hours,
                                    self.window.label_expire_in_minutes,
                                    self.window.input_spinbox_defaults_acknowledge_expire_duration_hours,
                                    self.window.input_spinbox_defaults_acknowledge_expire_duration_minutes]

    def initialize(self):
        # apply configuration values
        # start with servers tab
        self.window.tabs.setCurrentIndex(0)
        for widget in dir(self.window):
            if widget.startswith('input_'):
                if widget.startswith('input_checkbox_'):
                    if conf.__dict__[widget.split('input_checkbox_')[1]] is True:
                        self.window.__dict__[widget].toggle()
                elif widget.startswith('input_radiobutton_'):
                    if conf.__dict__[widget.split('input_radiobutton_')[1]] is True:
                        self.window.__dict__[widget].toggle()
                elif widget.startswith('input_lineedit_'):
                    # older versions of Nagstamon have a bool value for custom_action_separator
                    # which leads to a crash here - thus str() to solve this
                    self.window.__dict__[widget].setText(str(conf.__dict__[widget.split('input_lineedit_')[1]]))
                elif widget.startswith('input_spinbox_'):
                    self.window.__dict__[widget].setValue(int(conf.__dict__[widget.split('input_spinbox_')[1]]))
                elif widget.startswith('input_slider_'):
                    self.window.__dict__[widget].setValue(int(conf.__dict__[widget.split('input_slider_')[1]]))
            # bruteforce size smallification, lazy try/except variant
            try:
                self.window.__dict__[widget].adjustSize()
            except:
                pass
        # fill default order fields combobox with s names
        # kick out empty headers for hosts and services flags
        sort_fields = copy.copy(HEADERS_HEADERS)
        while '' in sort_fields:
            sort_fields.remove('')

        self.window.input_combobox_default_sort_field.addItems(sort_fields)
        # catch exception which will occur when older settings are used which have real header names as values
        try:
            self.window.input_combobox_default_sort_field.setCurrentText(HEADERS_KEYS_HEADERS[conf.default_sort_field])
        except Exception:
            self.window.input_combobox_default_sort_field.setCurrentText(conf.default_sort_field)

        # fill default sort order combobox
        self.window.input_combobox_default_sort_order.addItems(['Ascending', 'Descending'])
        # .title() to get upper first letter
        self.window.input_combobox_default_sort_order.setCurrentText(conf.default_sort_order.title())

        # fill combobox with screens for fullscreen
        for screen in app.screens():
            self.window.input_combobox_fullscreen_display.addItem(str(screen.name()))
        self.window.input_combobox_fullscreen_display.setCurrentText(str(conf.fullscreen_display))

        # fill servers listwidget with servers
        self.fill_list(self.window.list_servers, conf.servers)

        # select first item
        self.window.list_servers.setCurrentRow(0)

        # fill actions listwidget with actions
        self.fill_list(self.window.list_actions, conf.actions)

        # select first item
        self.window.list_actions.setCurrentRow(0)

        # paint colors onto color selection buttons and alternation example
        self.paint_colors()
        self.paint_color_alternation()
        self.change_color_alternation(conf.grid_alternation_intensity)

        # hide keyring setting if keyring is not available
        if KEYRING:
            self.window.input_checkbox_use_system_keyring.show()
        else:
            self.window.input_checkbox_use_system_keyring.hide()

        # hide 'Hide macOS Dock icon' if not on macOS
        if OS != OS_MACOS:
            self.window.input_checkbox_hide_macos_dock_icon.hide()

        # avoid showing offset setting if not icon in systray is configured
        if not OS in OS_NON_LINUX and not conf.icon_in_systray:
            self.toggle_systray_icon_offset()

        # important final size adjustment
        self.window.adjustSize()

    def show(self, tab=0):
        # hide them and thus be able to fix size if no extra Zabbix/Op5Monitor/IcingaWeb2 widgets are shown
        self.toggle_zabbix_widgets()
        self.toggle_op5monitor_widgets()
        self.toggle_expire_time_widgets()

        # small workaround for timestamp trick to avoid flickering
        # if the 'Settings' button was clicked too fast the timestamp difference
        # is too short and the statuswindow will keep open
        # modifying the timestamp could help
        statuswindow.is_shown_timestamp -= 1

        # tell the world that dialog pops up
        self.show_dialog.emit()

        # jump to requested tab in settings dialog
        self.window.tabs.setCurrentIndex(tab)

        # reset window if only needs smaller screen estate
        # self.window.adjustSize()
        # self.window.exec()
        super().show()

    @Slot()
    def show_new_server(self):
        """
            opens settings and new server dialogs - used by dialogs.server_missing
        """
        # emulate button click
        self.window.button_new_server.clicked.emit()

    @Slot()
    def show_filters(self):
        """
            opens filters settings after clicking button_filters in toparea
        """
        self.show(tab=2)

    @Slot()
    def show_defaults(self):
        """
            opens default settings after clicking button in acknowledge/downtime dialog
        """
        self.show(tab=6)

    def ok(self):
        """
            what to do if OK was pressed
        """
        global FONT, ICONS_FONT, statuswindow, menu, NUMBER_OF_DISPLAY_CHANGES

        # store position of statuswindow/statusbar only if statusbar is floating
        if conf.statusbar_floating:
            statuswindow.store_position_to_conf()

        # store hash of all display settings as display_mode to decide if statuswindow has to be recreated
        display_mode = str(conf.statusbar_floating) + \
                       str(conf.icon_in_systray) + \
                       str(conf.fullscreen) + \
                       str(conf.fullscreen_display) + \
                       str(conf.windowed)

        # do all stuff necessary after OK button was clicked
        # put widget values into conf
        for widget in self.window.__dict__.values():
            if widget.objectName().startswith('input_checkbox_'):
                conf.__dict__[widget.objectName().split('input_checkbox_')[1]] = widget.isChecked()
            elif widget.objectName().startswith('input_radiobutton_'):
                conf.__dict__[widget.objectName().split('input_radiobutton_')[1]] = widget.isChecked()
            elif widget.objectName().startswith("input_lineedit_"):
                conf.__dict__[widget.objectName().split('input_lineedit_')[1]] = widget.text()
            elif widget.objectName().startswith('input_spinbox_'):
                conf.__dict__[widget.objectName().split('input_spinbox_')[1]] = str(widget.value())
            elif widget.objectName().startswith('input_slider_'):
                conf.__dict__[widget.objectName().split('input_slider_')[1]] = str(widget.value())
            elif widget.objectName().startswith('input_combobox_'):
                conf.__dict__[widget.objectName().split('input_combobox_')[1]] = widget.currentText()
            elif widget.objectName().startswith('input_button_color_'):
                # get color value from color button stylesheet
                color = self.window.__dict__[widget.objectName()].styleSheet()
                color = color.split(':')[1].strip().split(';')[0]
                conf.__dict__[widget.objectName().split('input_button_')[1]] = color

        # convert some strings to integers and bools
        for item in conf.__dict__:
            if type(conf.__dict__[item]) == str:
                # when item is not one of those which always have to be strings then it might be OK to convert it
                if not item in CONFIG_STRINGS:
                    if conf.__dict__[item] in BOOLPOOL:
                        conf.__dict__[item] = BOOLPOOL[conf.__dict__[item]]
                    elif conf.__dict__[item].isdecimal():
                        conf.__dict__[item] = int(conf.__dict__[item])

        # start debug loop if debugging is enabled
        if conf.debug_mode:
            # only start debugging loop if it not already loops
            if statuswindow.worker.debug_loop_looping is False:
                self.start_debug_loop.emit()
        else:
            # set flag to tell debug loop it should stop please
            statuswindow.worker.debug_loop_looping = False

        # convert sorting fields to simple keys - maybe one day translated
        conf.default_sort_field = HEADERS_HEADERS_KEYS[conf.default_sort_field]

        # apply font
        conf.font = self.font.toString()
        # update global font and icons font
        FONT = self.font
        ICONS_FONT = QFont('Nagstamon', FONT.pointSize() + 2, QFont.Weight.Normal, False)

        # update brushes for treeview
        create_brushes()

        # save configuration
        conf.save_config()

        # when display mode was changed its the easiest to destroy the old status window and create a new one
        # store display_mode to decide if statuswindow has to be recreated
        if display_mode != str(conf.statusbar_floating) + \
                str(conf.icon_in_systray) + \
                str(conf.fullscreen) + \
                str(conf.fullscreen_display) + \
                str(conf.windowed):

            # increase number of display changes for silly Windows-hides-statusbar-after-display-mode-change problem
            NUMBER_OF_DISPLAY_CHANGES += 1

            # stop statuswindow workers
            statuswindow.worker.running = False
            statuswindow.worker_notification.running = False

            # hide window to avoid laggy GUI - better none than laggy
            statuswindow.hide()

            # tell all treeview threads to stop
            for server_vbox in statuswindow.servers_vbox.children():
                server_vbox.table.worker.finish.emit()

            # stop statuswindow workers
            statuswindow.worker.finish.emit()
            statuswindow.worker_notification.finish.emit()

            # kick out ol' statuswindow
            statuswindow.kill()

            # create new global one
            statuswindow = StatusWindow()

            # context menu for systray and statuswindow
            menu = MenuContext()

        # tell statuswindow to refresh due to new settings
        self.changed.emit()

        # see if there are any servers created and enabled
        check_servers()

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def cancel(self):
        """
            check if there are any usable servers configured
        """
        # call close and macOS dock icon treatment from ancestor
        super().cancel()
        check_servers()

    @Slot()
    def new_server(self):
        """
            create new server
        """
        dialogs.server.new()

    @Slot()
    def edit_server(self):
        """
            edit existing server
        """
        # issue #1114 - do not allow editing of servers when no server is selected nor doesn't exist
        if dialogs.settings.window.list_servers.currentItem():
            dialogs.server.edit()

    @Slot()
    def copy_server(self):
        """
            copy existing server
        """
        # issue #1114 - do not allow editing of servers when no server is selected nor doesn't exist
        if dialogs.settings.window.list_servers.currentItem():
            dialogs.server.copy()

    @Slot()
    def delete_server(self):
        """
            delete server, stop its thread, remove from config and list
        """
        # issue #1114 - do not allow editing of servers when no server is selected nor doesn't exist
        if dialogs.settings.window.list_servers.currentItem():
            # server to delete from current row in servers list
            server = conf.servers[self.window.list_servers.currentItem().text()]

            reply = QMessageBox.question(self.window, 'Nagstamon',
                                         f'Do you really want to delete monitor server <b>{server.name}</b>?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                # in case server is enabled delete its vbox
                if server.enabled:
                    for vbox in statuswindow.servers_vbox.children():
                        if vbox.server.name == server.name:
                            # stop thread by falsificate running flag
                            vbox.table.worker.running = False
                            vbox.table.worker.finish.emit()
                            break

                # kick server out of server instances
                servers.pop(server.name)
                # dito from config items
                conf.servers.pop(server.name)

                # refresh list
                # row index 0 to x
                row = self.window.list_servers.currentRow()
                # count real number, 1 to x
                count = self.window.list_servers.count()

                # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
                if row == count - 1:
                    # use the penultimate item as the new current one
                    row = count - 2
                else:
                    # go down one row
                    row = row + 1

                # refresh list and mark new current row
                self.refresh_list(list_widget=self.window.list_servers,
                                  list_conf=conf.servers,
                                  current=self.window.list_servers.item(row).text())
                del (row, count)

            # delete server config file from disk
            conf.delete_file('servers', 'server_{0}.conf'.format(quote(server.name, safe='')))
            del server

    def refresh_list(self, list_widget, list_conf, current=''):
        """
            refresh given 'list_widget' from given 'list_conf' and mark 'current' as current
        """
        # clear list of servers
        list_widget.clear()
        # fill servers listwidget with servers
        self.fill_list(list_widget, list_conf)
        # select current edited item
        # activate currently created/edited server monitor item by first searching it in the list
        list_widget.setCurrentItem(list_widget.findItems(current, Qt.MatchFlag.MatchExactly)[0])

    @Slot()
    def new_action(self):
        """
            create new action
        """
        dialogs.action.new()

    @Slot()
    def edit_action(self):
        """
            edit existing action
        """
        dialogs.action.edit()

    @Slot()
    def copy_action(self):
        """
            copy existing action and edit it
        """
        dialogs.action.copy()

    @Slot()
    def delete_action(self):
        """
            delete action remove from config and list
        """
        # action to delete from current row in actions list
        action = conf.actions[self.window.list_actions.currentItem().text()]

        reply = QMessageBox.question(self.window, 'Nagstamon',
                                     f'Do you really want to delete action <b>{action.name}</b>?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # kick action out of config items
            conf.actions.pop(action.name)

            # refresh list
            # row index 0 to x
            row = self.window.list_actions.currentRow()
            # count real number, 1 to x
            count = self.window.list_actions.count()

            # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
            if row == count - 1:
                # use the penultimate item as the new current one
                row = count - 2
            else:
                # go down one row
                row = row + 1

            # refresh list and mark new current row
            self.refresh_list(list_widget=self.window.list_actions, list_conf=conf.actions,
                              current=self.window.list_actions.item(row).text())

            del (row, count)

        # delete action config file from disk
        conf.delete_file('actions', 'action_{0}.conf'.format(quote(action.name, safe='')))
        del action

    def choose_sound_file_decoration(method):
        """
            try to decorate sound file dialog
        """

        def decoration_function(self):
            # execute decorated function
            method(self)
            # shortcut for widget to fill and revaluate
            widget = self.window.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # use 2 filters, sound files and all files
            file = dialogs.file_chooser.getOpenFileName(self.window,
                                                        filter='Sound files (*.mp3 *.MP3 *.mp4 *.MP4 '
                                                               '*.wav *.WAV *.ogg *.OGG);;'
                                                               'All files (*)')[0]

            # only take filename if QFileDialog gave something useful back
            if file != '':
                widget.setText(file)

        return (decoration_function)

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_warning(self):
        self.sound_file_type = 'warning'

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_critical(self):
        self.sound_file_type = 'critical'

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_down(self):
        self.sound_file_type = 'down'

    def play_sound_file_decoration(method):
        """
            try to decorate sound file dialog
        """

        def decoration_function(self):
            # execute decorated function
            method(self)
            # shortcut for widget to fill and revaluate
            widget = self.window.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # get file path from widget
            file = widget.text()

            # tell mediaplayer to play file only if it exists
            if mediaplayer.set_media(file) is True:
                mediaplayer.play()

        return (decoration_function)

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_warning(self):
        self.sound_file_type = 'warning'

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_critical(self):
        self.sound_file_type = 'critical'

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_down(self):
        self.sound_file_type = 'down'

    def paint_colors(self):
        """
            fill color selection buttons with appropriate colors
        """
        # color buttons
        for color in [x for x in conf.__dict__ if x.startswith('color_')]:
            self.window.__dict__['input_button_%s' % (color)].setStyleSheet('''background-color: %s;
                                                                           border-width: 1px;
                                                                           border-color: black;
                                                                           border-style: solid;'''
                                                                            % conf.__dict__[color])
        # example color labels
        for label in [x for x in self.window.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]
            self.window.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                      (conf.__dict__['color_%s_text' % (status)],
                                                       (conf.__dict__['color_%s_background' % (status)])))

    @Slot()
    def colors_defaults(self):
        """
            apply default colors to buttons
        """
        # color buttons
        for default_color in [x for x in conf.__dict__ if x.startswith('default_color_')]:
            # cut 'default_' off to get color
            color = default_color.split('default_')[1]
            self.window.__dict__['input_button_%s' % (color)].setStyleSheet('''background-color: %s;
                                                                           border-width: 1px;
                                                                           border-color: black;
                                                                           border-style: solid;'''
                                                                            % conf.__dict__[default_color])
        # example color labels
        for label in [x for x in self.window.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]

            # get color values from color button stylesheets
            color_text = self.window.__dict__['input_button_color_' + status + '_text'].styleSheet()
            color_text = color_text.split(':')[1].strip().split(';')[0]
            color_background = self.window.__dict__['input_button_color_' + status + '_background'].styleSheet()
            color_background = color_background.split(':')[1].strip().split(';')[0]

            # apply color values from stylesheet to label
            self.window.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                      (color_text, color_background))

    @Slot(str)
    def color_chooser(self, item):
        """
            open QColorDialog to choose a color and change it in settings dialog
        """
        color = conf.__dict__['color_%s' % (item)]

        new_color = QColorDialog.getColor(QColor(color), parent=self.window)
        # if canceled the color is invalid
        if new_color.isValid():
            self.window.__dict__['input_button_color_%s' % (item)].setStyleSheet('''background-color: %s;
                                                                                border-width: 1px;
                                                                                border-color: black;
                                                                                border-style: solid;'''
                                                                                 % new_color.name())
            status = item.split('_')[0]
            # get color value from stylesheet to paint example
            text = self.window.__dict__['input_button_color_%s_text' % (status)].styleSheet()
            text = text.split(':')[1].strip().split(';')[0]
            background = self.window.__dict__['input_button_color_%s_background' % (status)].styleSheet()
            background = background.split(':')[1].strip().split(';')[0]
            # set example color
            self.window.__dict__['label_color_%s' % (status)].setStyleSheet('''color: {0};
                                                                           background: {1}
                                                                        '''.format(text, background))
            # update alternation colors
            self.paint_color_alternation()
            self.change_color_alternation(self.window.input_slider_grid_alternation_intensity.value())

    def paint_color_alternation(self):
        """
            paint the intensity example color labels taking actual colors from color
            chooser buttons
            this labels have the color of alteration level 0 aka default
        """
        for state in COLORS:
            # get text color from button CSS
            text = self.window.__dict__['input_button_color_{0}_text'
            .format(state.lower())] \
                .styleSheet() \
                .split(';\n')[0].split(': ')[1]
            # get background color from button CSS
            background = self.window.__dict__['input_button_color_{0}_background'
            .format(state.lower())] \
                .styleSheet() \
                .split(';\n')[0].split(': ')[1]
            # set CSS
            self.window.__dict__['label_intensity_{0}_0'.format(state.lower())] \
                .setStyleSheet('''color: {0};
                                              background-color: {1};
                                              padding-top: 3px;
                                              padding-bottom: 3px;
                                              '''.format(text, background))

    @Slot(int)
    def change_color_alternation(self, value):
        """
            fill alternation level 1 labels with altered color
            derived from level 0 labels aka default
        """
        for state in COLORS:
            # only evaluate colors if there is any stylesheet
            if len(self.window.__dict__['input_button_color_{0}_text'
                    .format(state.lower())] \
                           .styleSheet()) > 0:

                # access both labels
                label_0 = self.window.__dict__['label_intensity_{0}_0'.format(state.lower())]
                label_1 = self.window.__dict__['label_intensity_{0}_1'.format(state.lower())]

                # get text color from text color chooser button
                text = self.window.__dict__['input_button_color_{0}_text'
                .format(state.lower())] \
                    .styleSheet() \
                    .split(';\n')[0].split(': ')[1]

                # get background of level 0 label
                background = label_0.palette().color(QPalette.ColorRole.Window)
                r, g, b, a = background.getRgb()

                # if label background is too dark lighten the color instead of darken it mor
                if background.lightness() < 30:
                    if value > 5:
                        r += 30
                        g += 30
                        b += 30
                    r = round(r / 100 * (100 + value))
                    g = round(g / 100 * (100 + value))
                    b = round(b / 100 * (100 + value))
                else:
                    r = round(r / 100 * (100 - value))
                    g = round(g / 100 * (100 - value))
                    b = round(b / 100 * (100 - value))

                # finally apply new background color
                # easier with style sheets than with QPalette/QColor
                label_1.setStyleSheet('''color: {0};
                                         background-color: rgb({1}, {2}, {3});
                                         padding-top: 3px;
                                         padding-bottom: 3px;
                                      '''.format(text, r, g, b))

    @Slot()
    def change_color_alternation_by_value(self):
        """
            to be fired up when colors are reset
        """
        self.change_color_alternation(self.window.input_slider_grid_alternation_intensity.value())

    @Slot()
    def font_chooser(self):
        """
            use font dialog to choose a font
        """
        self.font = QFontDialog.getFont(self.font, parent=self.window)[0]
        self.window.label_font.setFont(self.font)

    @Slot()
    def font_default(self):
        """
            reset font to default font which was valid when Nagstamon was launched
        """
        self.window.label_font.setFont(DEFAULT_FONT)
        self.font = DEFAULT_FONT

    @Slot()
    def button_check_for_new_version_clicked(self):
        """
            at this point start_mode for version check is definitively False
        """
        self.check_for_new_version.emit(False, self.window)

    @Slot()
    def choose_browser_executable(self):
        """
            show dialog for selection of non-default browser
        """
        # present dialog with OS-specific sensible defaults
        if OS == OS_WINDOWS:
            filter = 'Executables (*.exe *.EXE);; All files (*)'
            directory = os.environ['ProgramFiles']
        elif OS == OS_MACOS:
            filter = ''
            directory = '/Applications'
        else:
            filter = ''
            directory = '/usr/bin'

        file = dialogs.file_chooser.getOpenFileName(self.window,
                                                    directory=directory,
                                                    filter=filter)[0]

        # only take filename if QFileDialog gave something useful back
        if file != '':
            self.window.input_lineedit_custom_browser.setText(file)

    @Slot()
    def toggle_zabbix_widgets(self):
        """
            Depending on the existence of an enabled Zabbix monitor the Zabbix widgets are shown or hidden
        """
        use_zabbix = False
        for server in servers.values():
            if server.enabled:
                if server.type.startswith('Zabbix'):
                    use_zabbix = True
                    break
        # remove extra Zabbix options
        if use_zabbix:
            for widget in self.ZABBIX_WIDGETS:
                widget.show()
        else:
            for widget in self.ZABBIX_WIDGETS:
                widget.hide()
        # remove custom color intensity labels
        if use_zabbix and self.window.input_checkbox_grid_use_custom_intensity.isChecked():
            for widget in self.ZABBIX_COLOR_INTENSITY_LABELS:
                widget.show()
        else:
            for widget in self.ZABBIX_COLOR_INTENSITY_LABELS:
                widget.hide()

    @Slot()
    def toggle_op5monitor_widgets(self):
        """
            Depending on the existence of an enabled Op5Monitor monitor the Op5Monitor widgets are shown or hidden
        """
        use_op5monitor = False
        for server in servers.values():
            if server.enabled:
                if server.type == 'op5Monitor':
                    use_op5monitor = True
                    break
        if use_op5monitor:
            for widget in self.OP5MONITOR_WIDGETS:
                widget.show()
        else:
            for widget in self.OP5MONITOR_WIDGETS:
                widget.hide()

    @Slot()
    def toggle_expire_time_widgets(self):
        """
            Depending on the existence of an enabled IcingaWeb2 or Alertmanager monitor the expire_time widgets are shown or hidden
        """
        use_expire_time = False
        for server in servers.values():
            if server.enabled:
                if server.type in ['IcingaWeb2', 'Icinga2API', 'Alertmanager']:
                    use_expire_time = True
                    break
        if use_expire_time:
            for widget in self.EXPIRE_TIME_WIDGETS:
                widget.show()
        else:
            for widget in self.EXPIRE_TIME_WIDGETS:
                widget.hide()

    @Slot()
    def toggle_systray_icon_offset(self):
        """
            Only show offset spinbox when offset is enabled
        """
        if self.window.input_checkbox_systray_offset_use.isVisible():
            if self.window.input_checkbox_systray_offset_use.isChecked():
                self.window.input_spinbox_systray_offset.show()
                self.window.label_offset_statuswindow.show()
            else:
                self.window.input_spinbox_systray_offset.hide()
                self.window.label_offset_statuswindow.hide()
        else:
            self.window.input_spinbox_systray_offset.hide()
            self.window.label_offset_statuswindow.hide()
