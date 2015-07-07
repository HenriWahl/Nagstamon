# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog_authentication.ui'
#
# Created by: PyQt5 UI code generator 5.4.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(567, 259)
        self.gridLayout = QtWidgets.QGridLayout(Dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.input_lineedit_autologin_key = QtWidgets.QLineEdit(Dialog)
        self.input_lineedit_autologin_key.setObjectName("input_lineedit_autologin_key")
        self.gridLayout.addWidget(self.input_lineedit_autologin_key, 5, 1, 1, 1)
        self.input_checkbox_use_autologin = QtWidgets.QCheckBox(Dialog)
        self.input_checkbox_use_autologin.setObjectName("input_checkbox_use_autologin")
        self.gridLayout.addWidget(self.input_checkbox_use_autologin, 4, 1, 1, 1)
        self.label_password = QtWidgets.QLabel(Dialog)
        self.label_password.setObjectName("label_password")
        self.gridLayout.addWidget(self.label_password, 2, 0, 1, 1)
        self.label_username = QtWidgets.QLabel(Dialog)
        self.label_username.setObjectName("label_username")
        self.gridLayout.addWidget(self.label_username, 1, 0, 1, 1)
        self.label_autologin_key = QtWidgets.QLabel(Dialog)
        self.label_autologin_key.setObjectName("label_autologin_key")
        self.gridLayout.addWidget(self.label_autologin_key, 5, 0, 1, 1)
        self.input_lineedit_username = QtWidgets.QLineEdit(Dialog)
        self.input_lineedit_username.setObjectName("input_lineedit_username")
        self.gridLayout.addWidget(self.input_lineedit_username, 1, 1, 1, 1)
        self.input_lineedit_password = QtWidgets.QLineEdit(Dialog)
        self.input_lineedit_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_lineedit_password.setObjectName("input_lineedit_password")
        self.gridLayout.addWidget(self.input_lineedit_password, 2, 1, 1, 1)
        self.input_checkbox_save_password = QtWidgets.QCheckBox(Dialog)
        self.input_checkbox_save_password.setObjectName("input_checkbox_save_password")
        self.gridLayout.addWidget(self.input_checkbox_save_password, 3, 1, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.button_exit = QtWidgets.QPushButton(Dialog)
        self.button_exit.setObjectName("button_exit")
        self.horizontalLayout.addWidget(self.button_exit)
        self.button_disable = QtWidgets.QPushButton(Dialog)
        self.button_disable.setObjectName("button_disable")
        self.horizontalLayout.addWidget(self.button_disable)
        self.button = QtWidgets.QPushButton(Dialog)
        self.button.setObjectName("button")
        self.horizontalLayout.addWidget(self.button)
        self.gridLayout.addLayout(self.horizontalLayout, 6, 0, 1, 2)
        self.label_monitor = QtWidgets.QLabel(Dialog)
        self.label_monitor.setObjectName("label_monitor")
        self.gridLayout.addWidget(self.label_monitor, 0, 0, 1, 2)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Authentication"))
        self.input_checkbox_use_autologin.setText(_translate("Dialog", "Use autologin"))
        self.label_password.setText(_translate("Dialog", "Password:"))
        self.label_username.setText(_translate("Dialog", "Username:"))
        self.label_autologin_key.setText(_translate("Dialog", "Autologin key:"))
        self.input_checkbox_save_password.setText(_translate("Dialog", "Save password"))
        self.button_exit.setText(_translate("Dialog", "Exit Nagstamon"))
        self.button_disable.setText(_translate("Dialog", "Disable monitor"))
        self.button.setText(_translate("Dialog", "OK"))
        self.label_monitor.setText(_translate("Dialog", "Please supply the correct credentials."))

