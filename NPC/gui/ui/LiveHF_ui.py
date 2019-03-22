# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'LiveHF.ui'
#
# Created by: PyQt4 UI code generator 4.12.1
#
# WARNING! All changes made in this file will be lost!

try:
    from PyQt5 import QtCore, QtGui
except:
    from PyQt4 import QtCore, QtGui
#from PyQt4 import QtCore, QtGui

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

class Ui_HitFinding(object):
    def setupUi(self, HitFinding):
        HitFinding.setObjectName(_fromUtf8("HitFinding"))
        HitFinding.resize(622, 817)
        HitFinding.setFrameShape(QtGui.QFrame.StyledPanel)
        HitFinding.setFrameShadow(QtGui.QFrame.Raised)
        self.HitRateView = PlotWidget(HitFinding)
        self.HitRateView.setGeometry(QtCore.QRect(20, 20, 590, 400))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.HitRateView.sizePolicy().hasHeightForWidth())
        self.HitRateView.setSizePolicy(sizePolicy)
        self.HitRateView.setMinimumSize(QtCore.QSize(590, 400))
        self.HitRateView.setMaximumSize(QtCore.QSize(590, 400))
        self.HitRateView.setSizeIncrement(QtCore.QSize(1, 1))
        self.HitRateView.setObjectName(_fromUtf8("HitRateView"))
        self.groupBox_4 = QtGui.QGroupBox(HitFinding)
        self.groupBox_4.setGeometry(QtCore.QRect(20, 430, 581, 221))
        self.groupBox_4.setObjectName(_fromUtf8("groupBox_4"))
        self.label_24 = QtGui.QLabel(self.groupBox_4)
        self.label_24.setGeometry(QtCore.QRect(444, 71, 17, 21))
        self.label_24.setObjectName(_fromUtf8("label_24"))
        self.label_25 = QtGui.QLabel(self.groupBox_4)
        self.label_25.setGeometry(QtCore.QRect(444, 40, 17, 21))
        self.label_25.setObjectName(_fromUtf8("label_25"))
        self.ROIX1 = QtGui.QLineEdit(self.groupBox_4)
        self.ROIX1.setGeometry(QtCore.QRect(359, 40, 75, 21))
        self.ROIX1.setObjectName(_fromUtf8("ROIX1"))
        self.label_26 = QtGui.QLabel(self.groupBox_4)
        self.label_26.setGeometry(QtCore.QRect(326, 71, 25, 21))
        self.label_26.setObjectName(_fromUtf8("label_26"))
        self.ROIX2 = QtGui.QLineEdit(self.groupBox_4)
        self.ROIX2.setGeometry(QtCore.QRect(359, 71, 75, 21))
        self.ROIX2.setObjectName(_fromUtf8("ROIX2"))
        self.ROIY2 = QtGui.QLineEdit(self.groupBox_4)
        self.ROIY2.setGeometry(QtCore.QRect(471, 71, 76, 21))
        self.ROIY2.setObjectName(_fromUtf8("ROIY2"))
        self.ROIY1 = QtGui.QLineEdit(self.groupBox_4)
        self.ROIY1.setGeometry(QtCore.QRect(471, 40, 76, 21))
        self.ROIY1.setObjectName(_fromUtf8("ROIY1"))
        self.label_27 = QtGui.QLabel(self.groupBox_4)
        self.label_27.setGeometry(QtCore.QRect(326, 40, 25, 21))
        self.label_27.setObjectName(_fromUtf8("label_27"))
        self.label_28 = QtGui.QLabel(self.groupBox_4)
        self.label_28.setGeometry(QtCore.QRect(290, 40, 26, 21))
        self.label_28.setObjectName(_fromUtf8("label_28"))
        self.UpdateROI = QtGui.QPushButton(self.groupBox_4)
        self.UpdateROI.setGeometry(QtCore.QRect(330, 100, 121, 32))
        self.UpdateROI.setObjectName(_fromUtf8("UpdateROI"))
        self.npix = QtGui.QLineEdit(self.groupBox_4)
        self.npix.setGeometry(QtCore.QRect(100, 70, 51, 21))
        self.npix.setObjectName(_fromUtf8("npix"))
        self.label_22 = QtGui.QLabel(self.groupBox_4)
        self.label_22.setGeometry(QtCore.QRect(30, 39, 61, 21))
        self.label_22.setObjectName(_fromUtf8("label_22"))
        self.thresh = QtGui.QLineEdit(self.groupBox_4)
        self.thresh.setGeometry(QtCore.QRect(99, 39, 51, 21))
        self.thresh.setObjectName(_fromUtf8("thresh"))
        self.label_21 = QtGui.QLabel(self.groupBox_4)
        self.label_21.setGeometry(QtCore.QRect(30, 70, 61, 21))
        self.label_21.setObjectName(_fromUtf8("label_21"))
        self.clearHitRate = QtGui.QPushButton(self.groupBox_4)
        self.clearHitRate.setGeometry(QtCore.QRect(340, 150, 221, 32))
        self.clearHitRate.setObjectName(_fromUtf8("clearHitRate"))
        self.label_23 = QtGui.QLabel(self.groupBox_4)
        self.label_23.setGeometry(QtCore.QRect(30, 100, 61, 21))
        self.label_23.setObjectName(_fromUtf8("label_23"))
        self.ncpus = QtGui.QLineEdit(self.groupBox_4)
        self.ncpus.setGeometry(QtCore.QRect(100, 100, 51, 21))
        self.ncpus.setObjectName(_fromUtf8("ncpus"))
        self.ShowROI = QtGui.QPushButton(self.groupBox_4)
        self.ShowROI.setGeometry(QtCore.QRect(450, 100, 131, 32))
        self.ShowROI.setObjectName(_fromUtf8("ShowROI"))
        self.FastScan = QtGui.QRadioButton(self.groupBox_4)
        self.FastScan.setGeometry(QtCore.QRect(30, 140, 100, 20))
        self.FastScan.setChecked(True)
        self.FastScan.setObjectName(_fromUtf8("FastScan"))
        self.ShootNTrap = QtGui.QRadioButton(self.groupBox_4)
        self.ShootNTrap.setGeometry(QtCore.QRect(30, 170, 100, 20))
        self.ShootNTrap.setObjectName(_fromUtf8("ShootNTrap"))
        self.NShots = QtGui.QLineEdit(self.groupBox_4)
        self.NShots.setGeometry(QtCore.QRect(240, 170, 51, 21))
        self.NShots.setObjectName(_fromUtf8("NShots"))
        self.label_29 = QtGui.QLabel(self.groupBox_4)
        self.label_29.setGeometry(QtCore.QRect(170, 170, 61, 21))
        self.label_29.setObjectName(_fromUtf8("label_29"))
        self.HitLog = QtGui.QPlainTextEdit(HitFinding)
        self.HitLog.setGeometry(QtCore.QRect(20, 660, 581, 141))
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Courier New"))
        font.setPointSize(11)
        self.HitLog.setFont(font)
        self.HitLog.setObjectName(_fromUtf8("HitLog"))

        self.retranslateUi(HitFinding)
        QtCore.QMetaObject.connectSlotsByName(HitFinding)

    def retranslateUi(self, HitFinding):
        HitFinding.setWindowTitle(_translate("HitFinding", "Frame", None))
        self.groupBox_4.setTitle(_translate("HitFinding", "Hit Finding", None))
        self.label_24.setText(_translate("HitFinding", "Y2", None))
        self.label_25.setText(_translate("HitFinding", "Y1", None))
        self.ROIX1.setText(_translate("HitFinding", "0", None))
        self.label_26.setText(_translate("HitFinding", "X2", None))
        self.ROIX2.setText(_translate("HitFinding", "2167", None))
        self.ROIY2.setText(_translate("HitFinding", "2070", None))
        self.ROIY1.setText(_translate("HitFinding", "0", None))
        self.label_27.setText(_translate("HitFinding", "X1", None))
        self.label_28.setText(_translate("HitFinding", "ROI", None))
        self.UpdateROI.setText(_translate("HitFinding", "Reset ROI ", None))
        self.npix.setText(_translate("HitFinding", "10", None))
        self.label_22.setText(_translate("HitFinding", "Threshold", None))
        self.thresh.setText(_translate("HitFinding", "20", None))
        self.label_21.setText(_translate("HitFinding", "# Pixels", None))
        self.clearHitRate.setText(_translate("HitFinding", "Clear Plot", None))
        self.label_23.setText(_translate("HitFinding", "# Cpus", None))
        self.ncpus.setText(_translate("HitFinding", "1", None))
        self.ShowROI.setText(_translate("HitFinding", "Show ROI", None))
        self.FastScan.setText(_translate("HitFinding", "Fast Scan", None))
        self.ShootNTrap.setText(_translate("HitFinding", "Shoot\'N Trap", None))
        self.NShots.setText(_translate("HitFinding", "10", None))
        self.label_29.setText(_translate("HitFinding", "# Shots", None))

from pyqtgraph import PlotWidget
