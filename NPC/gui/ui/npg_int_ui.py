# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'npg_int.ui'
#
# Created: Tue May 26 17:51:53 2015
#      by: PyQt4 UI code generator 4.11.3
#
# WARNING! All changes made in this file will be lost!

#try:
# from PyQt5 import QtCore, QtGui
#except:
try:
    from PyQt5 import QtCore, QtGui
except:
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
        Intensities.resize(880, 330)
        self.textEdit = QtGui.QTextEdit(Intensities)
        self.textEdit.setEnabled(False)
        self.textEdit.setGeometry(QtCore.QRect(20, 20, 840, 290))
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Courier New"))
        font.setPointSize(11)
        self.textEdit.setFont(font)
        self.textEdit.setObjectName(_fromUtf8("textEdit"))

        self.retranslateUi(Intensities)
        QtCore.QMetaObject.connectSlotsByName(Intensities)

    def retranslateUi(self, Intensities):
        Intensities.setWindowTitle(_translate("Intensities", "Intensities", None))

