# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'XP_Params.ui'
#
# Created by: PyQt4 UI code generator 4.12
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

class Ui_Form(object):
    def setupUi(self, Form, Live):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(300, 190)
        Form.setMinimumSize(QtCore.QSize(300, 190))
        Form.setMaximumSize(QtCore.QSize(300, 190))
        self.groupBox_3 = QtGui.QGroupBox(Form)
        self.groupBox_3.setGeometry(QtCore.QRect(10, 10, 280, 170))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy)
        self.groupBox_3.setMinimumSize(QtCore.QSize(280, 170))
        self.groupBox_3.setMaximumSize(QtCore.QSize(280, 170))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.groupBox_3.setFont(font)
        self.groupBox_3.setTitle(_fromUtf8(""))
        self.groupBox_3.setObjectName(_fromUtf8("groupBox_3"))
        self.widget = QtGui.QWidget(self.groupBox_3)
        self.widget.setGeometry(QtCore.QRect(11, 11, 266, 180))
        self.widget.setObjectName(_fromUtf8("widget"))
        self.formLayout = QtGui.QFormLayout(self.widget)
        self.formLayout.setLabelAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.formLayout.setMargin(0)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.label_13 = QtGui.QLabel(self.widget)
        self.label_13.setMinimumSize(QtCore.QSize(100, 0))
        self.label_13.setObjectName(_fromUtf8("label_13"))
        self.horizontalLayout.addWidget(self.label_13)
        self.Detector = QtGui.QComboBox(self.widget)
        self.Detector.setObjectName(_fromUtf8("Detector"))
        self.horizontalLayout.addWidget(self.Detector)
        self.formLayout.setLayout(0, QtGui.QFormLayout.LabelRole, self.horizontalLayout)
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.distance = QtGui.QLineEdit(self.widget)
        self.distance.setMaximumSize(QtCore.QSize(60, 16777215))
        self.distance.setSizeIncrement(QtCore.QSize(0, 0))
        self.distance.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.distance.setObjectName(_fromUtf8("distance"))
        self.gridLayout.addWidget(self.distance, 0, 1, 1, 1)
        self.label_14 = QtGui.QLabel(self.widget)
        self.label_14.setObjectName(_fromUtf8("label_14"))
        self.gridLayout.addWidget(self.label_14, 1, 0, 1, 1)
        self.Wavelength = QtGui.QLineEdit(self.widget)
        self.Wavelength.setMaximumSize(QtCore.QSize(60, 16777215))
        self.Wavelength.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.Wavelength.setObjectName(_fromUtf8("Wavelength"))
        self.gridLayout.addWidget(self.Wavelength, 1, 1, 1, 1)
        self.label_16 = QtGui.QLabel(self.widget)
        self.label_16.setObjectName(_fromUtf8("label_16"))
        self.gridLayout.addWidget(self.label_16, 2, 0, 1, 1)
        self.beamX = QtGui.QLineEdit(self.widget)
        self.beamX.setMaximumSize(QtCore.QSize(60, 16777215))
        self.beamX.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.beamX.setObjectName(_fromUtf8("beamX"))
        self.gridLayout.addWidget(self.beamX, 2, 1, 1, 1)
        self.label_17 = QtGui.QLabel(self.widget)
        self.label_17.setObjectName(_fromUtf8("label_17"))
        self.gridLayout.addWidget(self.label_17, 3, 0, 1, 1)
        self.beamY = QtGui.QLineEdit(self.widget)
        self.beamY.setMaximumSize(QtCore.QSize(60, 16777215))
        self.beamY.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.beamY.setObjectName(_fromUtf8("beamY"))
        self.gridLayout.addWidget(self.beamY, 3, 1, 1, 1)
        self.label_15 = QtGui.QLabel(self.widget)
        self.label_15.setMaximumSize(QtCore.QSize(160, 16777215))
        self.label_15.setObjectName(_fromUtf8("label_15"))
        self.gridLayout.addWidget(self.label_15, 0, 0, 1, 1)
        self.formLayout.setLayout(1, QtGui.QFormLayout.LabelRole, self.gridLayout)

        self.retranslateUi(Form, Live)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form, Live):
        Form.setWindowTitle(_translate("Form", "Experimental Settings", None))
        self.label_13.setText(_translate("Form", "Detector", None))
        if not Live:
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.setItemText(0, _translate("Form", "Pilatus1M", None))
            self.Detector.setItemText(1, _translate("Form", "Pilatus2M", None))
            self.Detector.setItemText(2, _translate("Form", "Pilatus6M", None))
            self.Detector.setItemText(3, _translate("Form", "EIger1M", None))
            self.Detector.setItemText(4, _translate("Form", "Eiger4M", None))
            self.Detector.setItemText(5, _translate("Form", "Eiger16M", None))
            self.Detector.setItemText(6, _translate("Form", "MPCCD", None))
            self.Detector.setItemText(7, _translate("Form", "CSPAD", None))
            self.Detector.setItemText(8, _translate("Form", "RayonixMx225hs", None))
        else:
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.addItem(_fromUtf8(""))
            self.Detector.setItemText(0, _translate("Form", "EIger1M", None))
            self.Detector.setItemText(1, _translate("Form", "Eiger4M", None))
            self.Detector.setItemText(2, _translate("Form", "Eiger16M", None))
        self.distance.setText(_translate("Form", "100", None))
        self.label_14.setText(_translate("Form", "Wavelength (A)", None))
        self.Wavelength.setText(_translate("Form", "1", None))
        self.label_16.setText(_translate("Form", "Beam Center X", None))
        self.beamX.setText(_translate("Form", "1200", None))
        self.label_17.setText(_translate("Form", "Beam Center Y", None))
        self.beamY.setText(_translate("Form", "1200", None))
        self.label_15.setText(_translate("Form", "Detector distance  (mm)", None))


