# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'settings_action.ui'
#
# Created by: PyQt5 UI code generator 5.4.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_settings_action_dialog(object):
    def setupUi(self, settings_action_dialog):
        settings_action_dialog.setObjectName("settings_action_dialog")
        settings_action_dialog.resize(561, 717)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(settings_action_dialog.sizePolicy().hasHeightForWidth())
        settings_action_dialog.setSizePolicy(sizePolicy)
        self.gridLayout = QtWidgets.QGridLayout(settings_action_dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.input_lineedit_re_status_information_pattern = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_re_status_information_pattern.setObjectName("input_lineedit_re_status_information_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_status_information_pattern, 18, 0, 1, 7)
        self.input_radiobutton_close_popwin = QtWidgets.QRadioButton(settings_action_dialog)
        self.input_radiobutton_close_popwin.setObjectName("input_radiobutton_close_popwin")
        self.gridLayout.addWidget(self.input_radiobutton_close_popwin, 23, 0, 1, 7)
        self.label_monitor_type = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_monitor_type.sizePolicy().hasHeightForWidth())
        self.label_monitor_type.setSizePolicy(sizePolicy)
        self.label_monitor_type.setObjectName("label_monitor_type")
        self.gridLayout.addWidget(self.label_monitor_type, 4, 0, 1, 1)
        self.input_radiobutton_leave_popwin_open = QtWidgets.QRadioButton(settings_action_dialog)
        self.input_radiobutton_leave_popwin_open.setObjectName("input_radiobutton_leave_popwin_open")
        self.gridLayout.addWidget(self.input_radiobutton_leave_popwin_open, 24, 0, 1, 7)
        self.label_description = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_description.sizePolicy().hasHeightForWidth())
        self.label_description.setSizePolicy(sizePolicy)
        self.label_description.setObjectName("label_description")
        self.gridLayout.addWidget(self.label_description, 6, 0, 1, 1)
        self.label_action_type = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_action_type.sizePolicy().hasHeightForWidth())
        self.label_action_type.setSizePolicy(sizePolicy)
        self.label_action_type.setObjectName("label_action_type")
        self.gridLayout.addWidget(self.label_action_type, 1, 0, 1, 1)
        self.label_name = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_name.sizePolicy().hasHeightForWidth())
        self.label_name.setSizePolicy(sizePolicy)
        self.label_name.setObjectName("label_name")
        self.gridLayout.addWidget(self.label_name, 5, 0, 1, 1)
        self.label_string = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_string.sizePolicy().hasHeightForWidth())
        self.label_string.setSizePolicy(sizePolicy)
        self.label_string.setObjectName("label_string")
        self.gridLayout.addWidget(self.label_string, 7, 0, 1, 1)
        self.label_status_popup = QtWidgets.QLabel(settings_action_dialog)
        self.label_status_popup.setObjectName("label_status_popup")
        self.gridLayout.addWidget(self.label_status_popup, 21, 0, 1, 7)
        self.input_checkbox_enabled = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_enabled.setObjectName("input_checkbox_enabled")
        self.gridLayout.addWidget(self.input_checkbox_enabled, 0, 0, 1, 7)
        self.label_python_re = QtWidgets.QLabel(settings_action_dialog)
        self.label_python_re.setObjectName("label_python_re")
        self.gridLayout.addWidget(self.label_python_re, 19, 0, 1, 7)
        self.input_combobox_monitor_type = QtWidgets.QComboBox(settings_action_dialog)
        self.input_combobox_monitor_type.setObjectName("input_combobox_monitor_type")
        self.gridLayout.addWidget(self.input_combobox_monitor_type, 4, 1, 1, 1)
        self.label_target = QtWidgets.QLabel(settings_action_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_target.sizePolicy().hasHeightForWidth())
        self.label_target.setSizePolicy(sizePolicy)
        self.label_target.setObjectName("label_target")
        self.gridLayout.addWidget(self.label_target, 10, 0, 1, 1)
        self.label_help_type = QtWidgets.QLabel(settings_action_dialog)
        self.label_help_type.setObjectName("label_help_type")
        self.gridLayout.addWidget(self.label_help_type, 1, 2, 1, 1)
        self.input_lineedit_re_service_pattern = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_re_service_pattern.setObjectName("input_lineedit_re_service_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_service_pattern, 16, 0, 1, 7)
        self.input_combobox_action_type = QtWidgets.QComboBox(settings_action_dialog)
        self.input_combobox_action_type.setObjectName("input_combobox_action_type")
        self.gridLayout.addWidget(self.input_combobox_action_type, 1, 1, 1, 1)
        self.input_checkbox_filter_target_host = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_filter_target_host.setObjectName("input_checkbox_filter_target_host")
        self.gridLayout.addWidget(self.input_checkbox_filter_target_host, 10, 1, 1, 1)
        self.input_checkbox_filter_target_service = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_filter_target_service.setObjectName("input_checkbox_filter_target_service")
        self.gridLayout.addWidget(self.input_checkbox_filter_target_service, 11, 1, 1, 1)
        self.label_help_string_description = QtWidgets.QLabel(settings_action_dialog)
        self.label_help_string_description.setObjectName("label_help_string_description")
        self.gridLayout.addWidget(self.label_help_string_description, 8, 1, 1, 1)
        self.input_lineedit_name = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_name.setObjectName("input_lineedit_name")
        self.gridLayout.addWidget(self.input_lineedit_name, 5, 1, 1, 6)
        self.input_lineedit_description = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_description.setObjectName("input_lineedit_description")
        self.gridLayout.addWidget(self.input_lineedit_description, 6, 1, 1, 6)
        self.buttonBox = QtWidgets.QDialogButtonBox(settings_action_dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 25, 6, 1, 1)
        self.input_lineedit_string = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_string.setObjectName("input_lineedit_string")
        self.gridLayout.addWidget(self.input_lineedit_string, 7, 1, 1, 6)
        self.label_help_type_description = QtWidgets.QLabel(settings_action_dialog)
        self.label_help_type_description.setObjectName("label_help_type_description")
        self.gridLayout.addWidget(self.label_help_type_description, 3, 1, 1, 1)
        self.label_help_string = QtWidgets.QLabel(settings_action_dialog)
        self.label_help_string.setObjectName("label_help_string")
        self.gridLayout.addWidget(self.label_help_string, 4, 2, 1, 1)
        self.input_lineedit_re_host_pattern = QtWidgets.QLineEdit(settings_action_dialog)
        self.input_lineedit_re_host_pattern.setObjectName("input_lineedit_re_host_pattern")
        self.gridLayout.addWidget(self.input_lineedit_re_host_pattern, 14, 0, 1, 7)
        self.input_checkbox_re_host_enabled = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_host_enabled.setObjectName("input_checkbox_re_host_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_host_enabled, 13, 0, 1, 2)
        self.input_checkbox_re_service_enabled = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_service_enabled.setObjectName("input_checkbox_re_service_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_service_enabled, 15, 0, 1, 2)
        self.input_checkbox_re_status_information_enabled = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_status_information_enabled.setObjectName("input_checkbox_re_status_information_enabled")
        self.gridLayout.addWidget(self.input_checkbox_re_status_information_enabled, 17, 0, 1, 3)
        self.input_checkbox_re_host_reverse = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_host_reverse.setObjectName("input_checkbox_re_host_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_host_reverse, 13, 6, 1, 1)
        self.input_checkbox_re_service_reverse = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_service_reverse.setObjectName("input_checkbox_re_service_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_service_reverse, 15, 6, 1, 1)
        self.input_checkbox_re_status_information_reverse = QtWidgets.QCheckBox(settings_action_dialog)
        self.input_checkbox_re_status_information_reverse.setObjectName("input_checkbox_re_status_information_reverse")
        self.gridLayout.addWidget(self.input_checkbox_re_status_information_reverse, 17, 6, 1, 1)

        self.retranslateUi(settings_action_dialog)
        self.buttonBox.accepted.connect(settings_action_dialog.accept)
        self.buttonBox.rejected.connect(settings_action_dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(settings_action_dialog)

    def retranslateUi(self, settings_action_dialog):
        _translate = QtCore.QCoreApplication.translate
        settings_action_dialog.setWindowTitle(_translate("settings_action_dialog", "Dialog"))
        self.input_radiobutton_close_popwin.setText(_translate("settings_action_dialog", "Close status popup window after action"))
        self.label_monitor_type.setText(_translate("settings_action_dialog", "Monitor type:"))
        self.input_radiobutton_leave_popwin_open.setText(_translate("settings_action_dialog", "Leave status popup window open after action"))
        self.label_description.setText(_translate("settings_action_dialog", "Description:"))
        self.label_action_type.setText(_translate("settings_action_dialog", "Action type:"))
        self.label_name.setText(_translate("settings_action_dialog", "Name:"))
        self.label_string.setText(_translate("settings_action_dialog", "String:"))
        self.label_status_popup.setText(_translate("settings_action_dialog", "Status popup window:"))
        self.input_checkbox_enabled.setText(_translate("settings_action_dialog", "Enabled"))
        self.label_python_re.setText(_translate("settings_action_dialog", "<a href=http://docs.python.org/howto/regex.html>See Python Regular Expressions HOWTO for filtering details.</a>"))
        self.label_target.setText(_translate("settings_action_dialog", "Target:"))
        self.label_help_type.setText(_translate("settings_action_dialog", "Help"))
        self.input_checkbox_filter_target_host.setText(_translate("settings_action_dialog", "Host"))
        self.input_checkbox_filter_target_service.setText(_translate("settings_action_dialog", "Service"))
        self.label_help_string_description.setText(_translate("settings_action_dialog", "Available variables for action strings:\n"
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
        self.label_help_type_description.setText(_translate("settings_action_dialog", "Available action types:\n"
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
        self.label_help_string.setText(_translate("settings_action_dialog", "Help"))
        self.input_checkbox_re_host_enabled.setText(_translate("settings_action_dialog", "Regular expressions for hosts"))
        self.input_checkbox_re_service_enabled.setText(_translate("settings_action_dialog", "Regular expressions for services"))
        self.input_checkbox_re_status_information_enabled.setText(_translate("settings_action_dialog", "Regular expressions for status informations"))
        self.input_checkbox_re_host_reverse.setText(_translate("settings_action_dialog", "reverse"))
        self.input_checkbox_re_service_reverse.setText(_translate("settings_action_dialog", "reverse"))
        self.input_checkbox_re_status_information_reverse.setText(_translate("settings_action_dialog", "reverse"))

