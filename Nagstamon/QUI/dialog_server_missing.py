# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog_server_missing.ui'
#
# Created by: PyQt5 UI code generator 5.5.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_dialog_server_missing(object):
    def setupUi(self, dialog_server_missing):
        dialog_server_missing.setObjectName("dialog_server_missing")
        dialog_server_missing.resize(813, 263)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(dialog_server_missing.sizePolicy().hasHeightForWidth())
        dialog_server_missing.setSizePolicy(sizePolicy)
        dialog_server_missing.setMinimumSize(QtCore.QSize(350, 0))
        dialog_server_missing.setModal(True)
        self.verticalLayout = QtWidgets.QVBoxLayout(dialog_server_missing)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_no_server_configured = QtWidgets.QLabel(dialog_server_missing)
        self.label_no_server_configured.setWordWrap(True)
        self.label_no_server_configured.setObjectName("label_no_server_configured")
        self.verticalLayout.addWidget(self.label_no_server_configured)
        self.label_no_server_enabled = QtWidgets.QLabel(dialog_server_missing)
        self.label_no_server_enabled.setWordWrap(True)
        self.label_no_server_enabled.setObjectName("label_no_server_enabled")
        self.verticalLayout.addWidget(self.label_no_server_enabled)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.button_enable_server = QtWidgets.QPushButton(dialog_server_missing)
        self.button_enable_server.setObjectName("button_enable_server")
        self.horizontalLayout.addWidget(self.button_enable_server)
        self.button_create_server = QtWidgets.QPushButton(dialog_server_missing)
        self.button_create_server.setObjectName("button_create_server")
        self.horizontalLayout.addWidget(self.button_create_server)
        self.button_ignore = QtWidgets.QPushButton(dialog_server_missing)
        self.button_ignore.setObjectName("button_ignore")
        self.horizontalLayout.addWidget(self.button_ignore)
        self.button_exit = QtWidgets.QPushButton(dialog_server_missing)
        self.button_exit.setObjectName("button_exit")
        self.horizontalLayout.addWidget(self.button_exit)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(dialog_server_missing)
        QtCore.QMetaObject.connectSlotsByName(dialog_server_missing)

    def retranslateUi(self, dialog_server_missing):
        _translate = QtCore.QCoreApplication.translate
        dialog_server_missing.setWindowTitle(_translate("dialog_server_missing", "Nagstamon"))
        self.label_no_server_configured.setText(_translate("dialog_server_missing", "<html><head/><body><p>There are no configured servers yet.<br/></p></body></html>"))
        self.label_no_server_enabled.setText(_translate("dialog_server_missing", "<html><head/><body><p>There are no servers enabled.<br/></p></body></html>"))
        self.button_enable_server.setText(_translate("dialog_server_missing", "Enable server"))
        self.button_create_server.setText(_translate("dialog_server_missing", "Create new server"))
        self.button_ignore.setText(_translate("dialog_server_missing", "Ignore"))
        self.button_exit.setText(_translate("dialog_server_missing", "Exit"))

