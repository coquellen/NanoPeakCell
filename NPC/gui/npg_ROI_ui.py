# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'npg_ROI.ui'
#
# Created: Thu May 28 22:23:01 2015
#      by: PyQt4 UI code generator 4.11.3
#
# WARNING! All changes made in this file will be lost!

#try:
# from PyQt5 import QtCore, QtGui
#except:
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

class Ui_ROI(object):
    def setupUi(self, ROI):
        ROI.setObjectName(_fromUtf8("ROI"))
        ROI.resize(625, 300)
        self.horizontalLayout = QtGui.QHBoxLayout(ROI)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.graphicsView = GraphicsLayoutWidget(ROI)
        self.graphicsView.setObjectName(_fromUtf8("graphicsView"))
        self.horizontalLayout.addWidget(self.graphicsView)

        self.retranslateUi(ROI)
        QtCore.QMetaObject.connectSlotsByName(ROI)

    def retranslateUi(self, ROI):
        ROI.setWindowTitle(_translate("ROI", "Form", None))

from pyqtgraph import GraphicsLayoutWidget
