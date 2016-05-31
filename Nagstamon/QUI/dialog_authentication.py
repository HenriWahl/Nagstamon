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
        dialog_authentication.resize(350, 226)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(dialog_authentication.sizePolicy().hasHeightForWidth())
        dialog_authentication.setSizePolicy(sizePolicy)
        dialog_authentication.setMinimumSize(QtCore.QSize(350, 0))
        dialog_authentication.setModal(True)
        self.gridLayout = QtWidgets.QGridLayout(dialog_authentication)
        self.gridLayout.setObjectName("gridLayout")
        self.label_username = QtWidgets.QLabel(dialog_authentication)
        self.label_username.setObjectName("label_username")
        self.gridLayout.addWidget(self.label_username, 0, 0, 1, 1)
        self.label_autologin_key = QtWidgets.QLabel(dialog_authentication)
        self.label_autologin_key.setObjectName("label_autologin_key")
        self.gridLayout.addWidget(self.label_autologin_key, 6, 0, 1, 1)
        self.label_password = QtWidgets.QLabel(dialog_authentication)
        self.label_password.setObjectName("label_password")
        self.gridLayout.addWidget(self.label_password, 1, 0, 1, 1)
        self.input_lineedit_autologin_key = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_autologin_key.setObjectName("input_lineedit_autologin_key")
        self.gridLayout.addWidget(self.input_lineedit_autologin_key, 6, 1, 1, 1)
        self.input_lineedit_username = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_username.setFrame(True)
        self.input_lineedit_username.setObjectName("input_lineedit_username")
        self.gridLayout.addWidget(self.input_lineedit_username, 0, 1, 1, 1)
        self.input_lineedit_password = QtWidgets.QLineEdit(dialog_authentication)
        self.input_lineedit_password.setMinimumSize(QtCore.QSize(200, 0))
        self.input_lineedit_password.setBaseSize(QtCore.QSize(0, 0))
        self.input_lineedit_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_lineedit_password.setObjectName("input_lineedit_password")
        self.gridLayout.addWidget(self.input_lineedit_password, 1, 1, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.button_box = QtWidgets.QDialogButtonBox(dialog_authentication)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.button_box.setCenterButtons(False)
        self.button_box.setObjectName("button_box")
        self.horizontalLayout.addWidget(self.button_box)
        self.gridLayout.addLayout(self.horizontalLayout, 7, 0, 1, 2)
        self.input_checkbox_use_autologin = QtWidgets.QCheckBox(dialog_authentication)
        self.input_checkbox_use_autologin.setObjectName("input_checkbox_use_autologin")
        self.gridLayout.addWidget(self.input_checkbox_use_autologin, 4, 0, 1, 2)
        self.input_checkbox_save_password = QtWidgets.QCheckBox(dialog_authentication)
        self.input_checkbox_save_password.setObjectName("input_checkbox_save_password")
        self.gridLayout.addWidget(self.input_checkbox_save_password, 3, 0, 1, 2)

        self.retranslateUi(dialog_authentication)
        QtCore.QMetaObject.connectSlotsByName(dialog_authentication)

    def retranslateUi(self, dialog_authentication):
        _translate = QtCore.QCoreApplication.translate
        dialog_authentication.setWindowTitle(_translate("dialog_authentication", "Authentication"))
        self.label_username.setText(_translate("dialog_authentication", "Username:"))
        self.label_autologin_key.setText(_translate("dialog_authentication", "Autologin key:"))
        self.label_password.setText(_translate("dialog_authentication", "Password:"))
        self.input_checkbox_use_autologin.setText(_translate("dialog_authentication", "Use autologin"))
        self.input_checkbox_save_password.setText(_translate("dialog_authentication", "Save password"))

