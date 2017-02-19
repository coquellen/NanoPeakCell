# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'NPC/gui/npg_int.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_Intensities(object):
    def setupUi(self, Intensities):
        Intensities.setObjectName(_fromUtf8("Intensities"))
        Intensities.resize(900, 350)
        self.gridLayout = QtGui.QGridLayout(Intensities)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.textEdit = QtGui.QTextEdit(Intensities)
        self.textEdit.setEnabled(False)
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Courier New"))
        font.setPointSize(12)
        self.textEdit.setFont(font)
        self.textEdit.setObjectName(_fromUtf8("textEdit"))
        self.gridLayout.addWidget(self.textEdit, 0, 0, 1, 1)

        self.retranslateUi(Intensities)
        QtCore.QMetaObject.connectSlotsByName(Intensities)

    def retranslateUi(self, Intensities):
        Intensities.setWindowTitle(_translate("Intensities", "Form", None))

