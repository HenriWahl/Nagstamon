# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog_acknowledge.ui'
#
# Created by: PyQt5 UI code generator 5.5.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_dialog_acknowledge(object):
    def setupUi(self, dialog_acknowledge):
        dialog_acknowledge.setObjectName("dialog_acknowledge")
        dialog_acknowledge.resize(465, 274)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(dialog_acknowledge.sizePolicy().hasHeightForWidth())
        dialog_acknowledge.setSizePolicy(sizePolicy)
        dialog_acknowledge.setSizeGripEnabled(True)
        dialog_acknowledge.setModal(True)
        self.gridLayout = QtWidgets.QGridLayout(dialog_acknowledge)
        self.gridLayout.setObjectName("gridLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.button_change_defaults_acknowledge = QtWidgets.QPushButton(dialog_acknowledge)
        self.button_change_defaults_acknowledge.setObjectName("button_change_defaults_acknowledge")
        self.horizontalLayout.addWidget(self.button_change_defaults_acknowledge)
        self.button_box = QtWidgets.QDialogButtonBox(dialog_acknowledge)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.button_box.setObjectName("button_box")
        self.horizontalLayout.addWidget(self.button_box)
        self.gridLayout.addLayout(self.horizontalLayout, 7, 0, 1, 2)
        self.options_groupbox = QtWidgets.QGroupBox(dialog_acknowledge)
        self.options_groupbox.setObjectName("options_groupbox")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.options_groupbox)
        self.verticalLayout.setObjectName("verticalLayout")
        self.input_checkbox_sticky_acknowledgement = QtWidgets.QCheckBox(self.options_groupbox)
        self.input_checkbox_sticky_acknowledgement.setObjectName("input_checkbox_sticky_acknowledgement")
        self.verticalLayout.addWidget(self.input_checkbox_sticky_acknowledgement)
        self.input_checkbox_send_notification = QtWidgets.QCheckBox(self.options_groupbox)
        self.input_checkbox_send_notification.setObjectName("input_checkbox_send_notification")
        self.verticalLayout.addWidget(self.input_checkbox_send_notification)
        self.input_checkbox_persistent_comment = QtWidgets.QCheckBox(self.options_groupbox)
        self.input_checkbox_persistent_comment.setObjectName("input_checkbox_persistent_comment")
        self.verticalLayout.addWidget(self.input_checkbox_persistent_comment)
        self.input_checkbox_acknowledge_all_services = QtWidgets.QCheckBox(self.options_groupbox)
        self.input_checkbox_acknowledge_all_services.setObjectName("input_checkbox_acknowledge_all_services")
        self.verticalLayout.addWidget(self.input_checkbox_acknowledge_all_services)
        self.gridLayout.addWidget(self.options_groupbox, 5, 0, 1, 2)
        self.input_label_description = QtWidgets.QLabel(dialog_acknowledge)
        self.input_label_description.setObjectName("input_label_description")
        self.gridLayout.addWidget(self.input_label_description, 0, 0, 1, 2)
        self.input_lineedit_comment = QtWidgets.QLineEdit(dialog_acknowledge)
        self.input_lineedit_comment.setObjectName("input_lineedit_comment")
        self.gridLayout.addWidget(self.input_lineedit_comment, 4, 0, 1, 1)

        self.retranslateUi(dialog_acknowledge)
        self.button_box.accepted.connect(dialog_acknowledge.accept)
        self.button_box.rejected.connect(dialog_acknowledge.reject)
        QtCore.QMetaObject.connectSlotsByName(dialog_acknowledge)
        dialog_acknowledge.setTabOrder(self.input_lineedit_comment, self.input_checkbox_sticky_acknowledgement)
        dialog_acknowledge.setTabOrder(self.input_checkbox_sticky_acknowledgement, self.input_checkbox_send_notification)
        dialog_acknowledge.setTabOrder(self.input_checkbox_send_notification, self.input_checkbox_persistent_comment)
        dialog_acknowledge.setTabOrder(self.input_checkbox_persistent_comment, self.input_checkbox_acknowledge_all_services)
        dialog_acknowledge.setTabOrder(self.input_checkbox_acknowledge_all_services, self.button_change_defaults_acknowledge)

    def retranslateUi(self, dialog_acknowledge):
        _translate = QtCore.QCoreApplication.translate
        dialog_acknowledge.setWindowTitle(_translate("dialog_acknowledge", "Acknowledge"))
        self.button_change_defaults_acknowledge.setText(_translate("dialog_acknowledge", "Change acknowledgement defaults..."))
        self.options_groupbox.setTitle(_translate("dialog_acknowledge", "Options"))
        self.input_checkbox_sticky_acknowledgement.setText(_translate("dialog_acknowledge", "Sticky acknowledgement"))
        self.input_checkbox_send_notification.setText(_translate("dialog_acknowledge", "Send notification"))
        self.input_checkbox_persistent_comment.setText(_translate("dialog_acknowledge", "Persistent comment"))
        self.input_checkbox_acknowledge_all_services.setText(_translate("dialog_acknowledge", "Acknowledge all services on host"))
        self.input_label_description.setText(_translate("dialog_acknowledge", "description - set by QUI.py"))

