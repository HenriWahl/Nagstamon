# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog_authentication.ui'
#
# Created by: PyQt5 UI code generator 5.5.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_dialog_authentication(object):
    def setupUi(self, dialog_authentication):
        dialog_authentication.setObjectName("dialog_authentication")
        dialog_authentication.resize(453, 259)
        dialog_authentication.setModal(True)
        self.gridLayout = QtWidgets.QGridLayout(dialog_authentication)
        self.gridLayout.setObjectName("gridLayout")
        self.label_username = QtWidgets.QLabel(dialog_authentication)
        self.label_username.setObjectName("label_username")
        self.gridLayout.addWidget(self.label_username, 1, 0, 1, 1)
        self.label_autologin_key = QtWidgets.QLabel(dialog_authentication)
        self.label_autologin_key.setObjectName("label_autologin_key")
        self.gridLayout.addWidget(self.label_autologin_key, 5, 0, 1, 1)
        self.input_checkbox_use_autologin = QtWidgets.QCheckBox(dialog_authentication)
        self.input_checkbox_use_autologin.setObjectName("input_checkbox_use_autologin")
        self.gridLayout.addWidget(self.input_checkbox_use_autologin, 4, 1, 1, 1)
        self.label_password = QtWidgets.QLabel(dialog_authentication)
        self.label_password.setObjectName("label_password")
        self.gridLayout.addWidget(self.label_password, 2, 0, 1, 1)
        self.input_lineedit_autologin_key = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_autologin_key.setObjectName("input_lineedit_autologin_key")
        self.gridLayout.addWidget(self.input_lineedit_autologin_key, 5, 1, 1, 1)
        self.input_lineedit_password = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_lineedit_password.setObjectName("input_lineedit_password")
        self.gridLayout.addWidget(self.input_lineedit_password, 2, 1, 1, 1)
        self.input_checkbox_save_password = QtWidgets.QCheckBox(dialog_authentication)
        self.input_checkbox_save_password.setObjectName("input_checkbox_save_password")
        self.gridLayout.addWidget(self.input_checkbox_save_password, 3, 1, 1, 1)
        self.input_lineedit_username = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_username.setObjectName("input_lineedit_username")
        self.gridLayout.addWidget(self.input_lineedit_username, 1, 1, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.button_exit = QtWidgets.QPushButton(dialog_authentication)
        self.button_exit.setObjectName("button_exit")
        self.horizontalLayout.addWidget(self.button_exit)
        self.button_disable = QtWidgets.QPushButton(dialog_authentication)
        self.button_disable.setObjectName("button_disable")
        self.horizontalLayout.addWidget(self.button_disable)
        self.button_box = QtWidgets.QDialogButtonBox(dialog_authentication)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.button_box.setCenterButtons(False)
        self.button_box.setObjectName("button_box")
        self.horizontalLayout.addWidget(self.button_box)
        self.gridLayout.addLayout(self.horizontalLayout, 6, 0, 1, 2)
        self.label_monitor = QtWidgets.QLabel(dialog_authentication)
        self.label_monitor.setObjectName("label_monitor")
        self.gridLayout.addWidget(self.label_monitor, 0, 0, 1, 2)

        self.retranslateUi(dialog_authentication)
        QtCore.QMetaObject.connectSlotsByName(dialog_authentication)

    def retranslateUi(self, dialog_authentication):
        _translate = QtCore.QCoreApplication.translate
        dialog_authentication.setWindowTitle(_translate("dialog_authentication", "Authentication"))
        self.label_username.setText(_translate("dialog_authentication", "Username:"))
        self.label_autologin_key.setText(_translate("dialog_authentication", "Autologin key:"))
        self.input_checkbox_use_autologin.setText(_translate("dialog_authentication", "Use autologin"))
        self.label_password.setText(_translate("dialog_authentication", "Password:"))
        self.input_checkbox_save_password.setText(_translate("dialog_authentication", "Save password"))
        self.button_exit.setText(_translate("dialog_authentication", "Exit Nagstamon"))
        self.button_disable.setText(_translate("dialog_authentication", "Disable monitor"))
        self.label_monitor.setText(_translate("dialog_authentication", "Please supply the correct credentials."))

