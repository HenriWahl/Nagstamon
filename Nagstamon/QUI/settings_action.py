# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'settings_action.ui'
#
# Created by: PyQt5 UI code generator 5.8.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_settings_action(object):
    def setupUi(self, settings_action):
        settings_action.setObjectName("settings_action")
        settings_action.resize(555, 849)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(settings_action.sizePolicy().hasHeightForWidth())
        settings_action.setSizePolicy(sizePolicy)
        settings_action.setModal(True)
        self.gridLayout = QtWidgets.QGridLayout(settings_action)
        self.gridLayout.setObjectName("gridLayout")
        self.input_radiobutton_close_popwin = QtWidgets.QRadioButton(settings_action)
        self.input_radiobutton_close_popwin.setObjectName("input_radiobutton_close_popwin")
        self.gridLayout.addWidget(self.input_radiobutton_close_popwin, 31, 0, 1, 6)
        self.label_monitor_type = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_monitor_type.sizePolicy().hasHeightForWidth())
        self.label_monitor_type.setSizePolicy(sizePolicy)
        self.label_monitor_type.setObjectName("label_monitor_type")
        self.gridLayout.addWidget(self.label_monitor_type, 3, 0, 1, 1)
        self.label_target = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_target.sizePolicy().hasHeightForWidth())
        self.label_target.setSizePolicy(sizePolicy)
        self.label_target.setObjectName("label_target")
        self.gridLayout.addWidget(self.label_target, 13, 0, 1, 1)
        self.input_checkbox_re_host_reverse = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_host_reverse.setObjectName("input_checkbox_re_host_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_host_reverse, 22, 5, 1, 1)
        self.label_action_type = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_action_type.sizePolicy().hasHeightForWidth())
        self.label_action_type.setSizePolicy(sizePolicy)
        self.label_action_type.setObjectName("label_action_type")
        self.gridLayout.addWidget(self.label_action_type, 1, 0, 1, 1)
        self.label_name = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_name.sizePolicy().hasHeightForWidth())
        self.label_name.setSizePolicy(sizePolicy)
        self.label_name.setObjectName("label_name")
        self.gridLayout.addWidget(self.label_name, 4, 0, 1, 1)
        self.input_lineedit_re_service_pattern = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_re_service_pattern.setObjectName("input_lineedit_re_service_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_service_pattern, 24, 0, 1, 5)
        self.input_checkbox_re_service_reverse = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_service_reverse.setObjectName("input_checkbox_re_service_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_service_reverse, 24, 5, 1, 1)
        self.input_lineedit_description = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_description.setObjectName("input_lineedit_description")
        self.gridLayout.addWidget(self.input_lineedit_description, 5, 1, 1, 5)
        self.button_box = QtWidgets.QDialogButtonBox(settings_action)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.button_box.setObjectName("button_box")
        self.gridLayout.addWidget(self.button_box, 34, 0, 1, 6)
        self.input_lineedit_re_status_information_pattern = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_re_status_information_pattern.setObjectName("input_lineedit_re_status_information_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_status_information_pattern, 26, 0, 1, 5)
        self.input_checkbox_re_status_information_reverse = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_status_information_reverse.setObjectName("input_checkbox_re_status_information_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_status_information_reverse, 26, 5, 1, 1)
        self.input_lineedit_re_duration_pattern = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_re_duration_pattern.setObjectName("input_lineedit_re_duration_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_duration_pattern, 28, 0, 1, 5)
        self.input_checkbox_re_duration_reverse = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_duration_reverse.setObjectName("input_checkbox_re_duration_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_duration_reverse, 28, 5, 1, 1)
        self.input_lineedit_re_attempt_pattern = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_re_attempt_pattern.setObjectName("input_lineedit_re_attempt_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_attempt_pattern, 30, 0, 1, 5)
        self.input_checkbox_re_attempt_reverse = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_attempt_reverse.setObjectName("input_checkbox_re_attempt_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_attempt_reverse, 30, 5, 1, 1)
        self.input_textedit_string = QtWidgets.QTextEdit(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.input_textedit_string.sizePolicy().hasHeightForWidth())
        self.input_textedit_string.setSizePolicy(sizePolicy)
        self.input_textedit_string.setObjectName("input_textedit_string")
        self.gridLayout.addWidget(self.input_textedit_string, 6, 1, 1, 5)
        self.input_checkbox_filter_target_host = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_filter_target_host.setObjectName("input_checkbox_filter_target_host")
        self.gridLayout.addWidget(self.input_checkbox_filter_target_host, 13, 1, 1, 1)
        self.label_description = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_description.sizePolicy().hasHeightForWidth())
        self.label_description.setSizePolicy(sizePolicy)
        self.label_description.setObjectName("label_description")
        self.gridLayout.addWidget(self.label_description, 5, 0, 1, 1)
        self.input_radiobutton_leave_popwin_open = QtWidgets.QRadioButton(settings_action)
        self.input_radiobutton_leave_popwin_open.setObjectName("input_radiobutton_leave_popwin_open")
        self.gridLayout.addWidget(self.input_radiobutton_leave_popwin_open, 32, 0, 1, 6)
        self.label_string = QtWidgets.QLabel(settings_action)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_string.sizePolicy().hasHeightForWidth())
        self.label_string.setSizePolicy(sizePolicy)
        self.label_string.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.label_string.setObjectName("label_string")
        self.gridLayout.addWidget(self.label_string, 6, 0, 1, 1)
        self.input_lineedit_name = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_name.setObjectName("input_lineedit_name")
        self.gridLayout.addWidget(self.input_lineedit_name, 4, 1, 1, 5)
        self.input_checkbox_filter_target_service = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_filter_target_service.setObjectName("input_checkbox_filter_target_service")
        self.gridLayout.addWidget(self.input_checkbox_filter_target_service, 14, 1, 1, 1)
        self.input_combobox_monitor_type = QtWidgets.QComboBox(settings_action)
        self.input_combobox_monitor_type.setObjectName("input_combobox_monitor_type")
        self.gridLayout.addWidget(self.input_combobox_monitor_type, 3, 1, 1, 2)
        self.input_combobox_type = QtWidgets.QComboBox(settings_action)
        self.input_combobox_type.setObjectName("input_combobox_type")
        self.gridLayout.addWidget(self.input_combobox_type, 1, 1, 1, 2)
        self.input_lineedit_re_host_pattern = QtWidgets.QLineEdit(settings_action)
        self.input_lineedit_re_host_pattern.setObjectName("input_lineedit_re_host_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_host_pattern, 22, 0, 1, 5)
        self.input_checkbox_re_host_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_host_enabled.setObjectName("input_checkbox_re_host_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_host_enabled, 21, 0, 1, 6)
        self.input_checkbox_re_service_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_service_enabled.setObjectName("input_checkbox_re_service_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_service_enabled, 23, 0, 1, 6)
        self.input_checkbox_re_status_information_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_status_information_enabled.setObjectName("input_checkbox_re_status_information_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_status_information_enabled, 25, 0, 1, 6)
        self.input_checkbox_re_duration_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_duration_enabled.setObjectName("input_checkbox_re_duration_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_duration_enabled, 27, 0, 1, 6)
        self.input_checkbox_re_attempt_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_re_attempt_enabled.setObjectName("input_checkbox_re_attempt_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_attempt_enabled, 29, 0, 1, 6)
        self.label_python_re = QtWidgets.QLabel(settings_action)
        self.label_python_re.setOpenExternalLinks(True)
        self.label_python_re.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.label_python_re.setObjectName("label_python_re")
        self.gridLayout.addWidget(self.label_python_re, 31, 0, 1, 6)
        self.label_status_popup = QtWidgets.QLabel(settings_action)
        self.label_status_popup.setObjectName("label_status_popup")
        self.gridLayout.addWidget(self.label_status_popup, 30, 0, 1, 6)
        self.input_checkbox_recheck = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_recheck.setObjectName("input_checkbox_recheck")
        self.gridLayout.addWidget(self.input_checkbox_recheck, 33, 0, 1, 6)
        self.input_checkbox_enabled = QtWidgets.QCheckBox(settings_action)
        self.input_checkbox_enabled.setObjectName("input_checkbox_enabled")
        self.gridLayout.addWidget(self.input_checkbox_enabled, 0, 0, 1, 6)

        self.retranslateUi(settings_action)
        self.button_box.accepted.connect(settings_action.accept)
        self.button_box.rejected.connect(settings_action.reject)
        QtCore.QMetaObject.connectSlotsByName(settings_action)
        settings_action.setTabOrder(self.input_checkbox_enabled, self.input_combobox_type)
        settings_action.setTabOrder(self.input_combobox_type, self.input_combobox_monitor_type)
        settings_action.setTabOrder(self.input_combobox_monitor_type, self.input_lineedit_name)
        settings_action.setTabOrder(self.input_lineedit_name, self.input_lineedit_description)
        settings_action.setTabOrder(self.input_lineedit_description, self.input_checkbox_filter_target_host)
        settings_action.setTabOrder(self.input_checkbox_filter_target_host, self.input_checkbox_filter_target_service)
        settings_action.setTabOrder(self.input_checkbox_filter_target_service, self.input_checkbox_re_host_enabled)
        settings_action.setTabOrder(self.input_checkbox_re_host_enabled, self.input_lineedit_re_host_pattern)
        settings_action.setTabOrder(self.input_lineedit_re_host_pattern, self.input_checkbox_re_host_reverse)
        settings_action.setTabOrder(self.input_checkbox_re_host_reverse, self.input_checkbox_re_service_enabled)
        settings_action.setTabOrder(self.input_checkbox_re_service_enabled, self.input_lineedit_re_service_pattern)
        settings_action.setTabOrder(self.input_lineedit_re_service_pattern, self.input_checkbox_re_service_reverse)
        settings_action.setTabOrder(self.input_checkbox_re_service_reverse, self.input_checkbox_re_status_information_enabled)
        settings_action.setTabOrder(self.input_checkbox_re_status_information_enabled, self.input_lineedit_re_status_information_pattern)
        settings_action.setTabOrder(self.input_lineedit_re_status_information_pattern, self.input_checkbox_re_status_information_reverse)
        settings_action.setTabOrder(self.input_checkbox_re_status_information_reverse, self.input_checkbox_re_duration_enabled)
        settings_action.setTabOrder(self.input_checkbox_re_duration_enabled, self.input_lineedit_re_duration_pattern)
        settings_action.setTabOrder(self.input_lineedit_re_duration_pattern, self.input_checkbox_re_duration_reverse)
        settings_action.setTabOrder(self.input_checkbox_re_duration_reverse, self.input_checkbox_re_attempt_enabled)
        settings_action.setTabOrder(self.input_checkbox_re_attempt_enabled, self.input_lineedit_re_attempt_pattern)
        settings_action.setTabOrder(self.input_lineedit_re_attempt_pattern, self.input_checkbox_re_attempt_reverse)
        settings_action.setTabOrder(self.input_checkbox_re_attempt_reverse, self.input_radiobutton_close_popwin)
        settings_action.setTabOrder(self.input_radiobutton_close_popwin, self.input_radiobutton_leave_popwin_open)

    def retranslateUi(self, settings_action):
        _translate = QtCore.QCoreApplication.translate
        settings_action.setWindowTitle(_translate("settings_action", "Dialog"))
        self.input_radiobutton_close_popwin.setText(_translate("settings_action", "Close status popup window after action"))
        self.label_monitor_type.setText(_translate("settings_action", "Monitor type:"))
        self.label_target.setText(_translate("settings_action", "Target:"))
        self.input_checkbox_re_host_reverse.setText(_translate("settings_action", "reverse"))
        self.label_action_type.setText(_translate("settings_action", "Action type:"))
        self.input_checkbox_re_status_information_reverse.setText(_translate("settings_action", "reverse"))
        self.input_checkbox_re_duration_reverse.setText(_translate("settings_action", "reverse"))
        self.input_checkbox_re_attempt_reverse.setText(_translate("settings_action", "reverse"))
        self.label_name.setText(_translate("settings_action", "Name:"))
        self.input_checkbox_re_service_reverse.setText(_translate("settings_action", "reverse"))
        self.input_textedit_string.setToolTip(_translate("settings_action", "Available variables for action strings:\n"
"\n"
"$HOST$ - host as in monitor\n"
"$SERVICE$ - service as in monitor\n"
"$MONITOR$ - monitor address\n"
"$MONITOR-CGI$ - monitor CGI address\n"
"$ADDRESS$ - address of host, delivered from connection method\n"
"$USERNAME$ - username on monitor\n"
"$STATUS-INFO$ - status information for host or service\n"
"$PASSWORD$ - username\'s password on monitor\n"
"$COMMENT-ACK$ - default acknowledge comment\n"
"$COMMENT-DOWN$ - default downtime comment\n"
"$COMMENT-SUBMIT$ - default submit check result comment\n"
"\n"
"$TRANSID$ - only useful for Check_MK as _transid=$TRANSID$"))
        self.input_checkbox_filter_target_host.setText(_translate("settings_action", "Host"))
        self.label_description.setText(_translate("settings_action", "Description:"))
        self.input_radiobutton_leave_popwin_open.setText(_translate("settings_action", "Leave status popup window open after action"))
        self.label_string.setText(_translate("settings_action", "String:"))
        self.input_checkbox_filter_target_service.setText(_translate("settings_action", "Service"))
        self.input_combobox_type.setToolTip(_translate("settings_action", "Available action types:\n"
"\n"
"Browser:\n"
"Use given string as URL, evaluate variables and open it in your default browser, for example a graph page in monitor.\n"
"\n"
"Command:\n"
"Execute command as given in string and evaluate variables, for example to open SSH connection.\n"
"\n"
"URL:\n"
"Request given URL string in the background, for example to acknowledge a service with one click.\n"
""))
        self.input_checkbox_re_host_enabled.setText(_translate("settings_action", "Regular expressions for hosts"))
        self.input_checkbox_re_service_enabled.setText(_translate("settings_action", "Regular expressions for services"))
        self.input_checkbox_re_status_information_enabled.setText(_translate("settings_action", "Regular expressions for status informations"))
        self.input_checkbox_re_duration_enabled.setText(_translate("settings_action", "Regular expressions for duration"))
        self.input_checkbox_re_attempt_enabled.setText(_translate("settings_action", "Regular expressions for attempt"))
        self.label_python_re.setText(_translate("settings_action", "<a href=http://docs.python.org/howto/regex.html>See Python Regular Expressions HOWTO for filtering details.</a>"))
        self.label_status_popup.setText(_translate("settings_action", "Status popup window:"))
        self.input_checkbox_recheck.setText(_translate("settings_action", "Recheck after action to force result"))
        self.input_checkbox_enabled.setText(_translate("settings_action", "Enabled"))

