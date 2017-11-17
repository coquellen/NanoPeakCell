# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'FileTree.ui'
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
    def setupUi(self, Form):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(394, 778)
        Form.setMinimumSize(QtCore.QSize(394, 778))
        self.verticalLayout = QtGui.QVBoxLayout(Form)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.groupBox_5 = QtGui.QGroupBox(Form)
        self.groupBox_5.setMinimumSize(QtCore.QSize(300, 0))
        self.groupBox_5.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.groupBox_5.setTitle(_fromUtf8(""))
        self.groupBox_5.setObjectName(_fromUtf8("groupBox_5"))
        self.verticalLayout_7 = QtGui.QVBoxLayout(self.groupBox_5)
        self.verticalLayout_7.setObjectName(_fromUtf8("verticalLayout_7"))
        self.treeWidget = TestListView(self.groupBox_5)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.treeWidget.sizePolicy().hasHeightForWidth())
        self.treeWidget.setSizePolicy(sizePolicy)
        self.treeWidget.setMinimumSize(QtCore.QSize(274, 500))
        self.treeWidget.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.treeWidget.setAcceptDrops(True)
        self.treeWidget.setLineWidth(1)
        self.treeWidget.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.treeWidget.setDefaultDropAction(QtCore.Qt.CopyAction)
        self.treeWidget.setAlternatingRowColors(False)
        self.treeWidget.setIndentation(20)
        self.treeWidget.setUniformRowHeights(True)
        self.treeWidget.setObjectName(_fromUtf8("treeWidget"))
        self.treeWidget.header().setVisible(True)
        self.treeWidget.header().setDefaultSectionSize(270)
        self.verticalLayout_7.addWidget(self.treeWidget)
        self.horizontalLayout_7 = QtGui.QHBoxLayout()
        self.horizontalLayout_7.setObjectName(_fromUtf8("horizontalLayout_7"))
        self.LoadResultsBut = QtGui.QPushButton(self.groupBox_5)
        self.LoadResultsBut.setObjectName(_fromUtf8("LoadResultsBut"))
        self.horizontalLayout_7.addWidget(self.LoadResultsBut)
        self.PlayButton = QtGui.QPushButton(self.groupBox_5)
        self.PlayButton.setObjectName(_fromUtf8("PlayButton"))
        self.horizontalLayout_7.addWidget(self.PlayButton)
        self.StopButton = QtGui.QPushButton(self.groupBox_5)
        self.StopButton.setObjectName(_fromUtf8("StopButton"))
        self.horizontalLayout_7.addWidget(self.StopButton)
        self.verticalLayout_7.addLayout(self.horizontalLayout_7)
        self.verticalLayout.addWidget(self.groupBox_5)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "Files", None))
        self.treeWidget.headerItem().setText(0, _translate("Form", "Filename", None))
        self.treeWidget.headerItem().setText(1, _translate("Form", "# Frames", None))
        self.LoadResultsBut.setText(_translate("Form", "Load Images...", None))
        self.PlayButton.setText(_translate("Form", "Play", None))
        self.StopButton.setText(_translate("Form", "Stop", None))

from NPC.gui.NPC_Widgets import TestListView
