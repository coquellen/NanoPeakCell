
from PyQt4 import QtCore, QtGui
import sys

class EditButtonsWidget(QtGui.QWidget):
    editCalled = QtCore.pyqtSignal(str)
    def __init__(self, row, col, parent=None,):
        super(EditButtonsWidget,self).__init__(parent)
        self.row = row
        self.col = col
        self.parent = parent
        btnsave = QtGui.QPushButton('Save')
        btnedit = QtGui.QPushButton('edit')
        btndelete = QtGui.QPushButton('delete')
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(btnsave)
        layout.addWidget(btnedit)
        layout.addWidget(btndelete)
        self.setLayout(layout)
        btnedit.clicked.connect(self.getAllCellVal)

    @QtCore.pyqtSlot()
    def getAllCellVal(self):
        itmVal = {}
        for col in range(0, 4):
            itm = self.parent.item(self.row, col).text()
            itmVal[col] = str(itm)
        if itmVal:
            self.editCalled.emit(str(itmVal))


class MainForm(QtGui.QDialog):
    def __init__(self,parent=None):
        super(MainForm,self).__init__(parent)
        self.resize(400,200)
        self.tableWidget = QtGui.QTableWidget()

        layout = QtGui.QVBoxLayout()
        layout.addWidget( self.tableWidget)
        self.setLayout(layout)
        self.init_main_form()

    def bb(self):
        button = QtGui.QApplication.focusWidget()
        print(button.pos())
        index = self.tableWidget.indexAt(button.pos())
        if index.isValid():
            print(index.row(), index.column())

    def printEditVal(self, values):
        print values

    def init_main_form(self):
        data =[['a','b','c','d'],['z','y','x','w']]
        self.tableWidget.setColumnCount(5)
        for row in data:
            inx = data.index(row)
            self.tableWidget.insertRow(inx)
            self.tableWidget.setItem(inx,0,QtGui.QTableWidgetItem(str(row[0])))
            self.tableWidget.setItem(inx,1,QtGui.QTableWidgetItem(str(row[1])))
            self.tableWidget.setItem(inx,2,QtGui.QTableWidgetItem(str(row[2])))
            self.tableWidget.setItem(inx,3,QtGui.QTableWidgetItem(str(row[3])))
            buttonWid = EditButtonsWidget(inx,4, self.tableWidget)
            buttonWid.editCalled.connect(self.printEditVal)
            self.tableWidget.setCellWidget(inx,4,buttonWid)


def main():
    app = QtGui.QApplication(sys.argv)
    main_form = MainForm()
    main_form.show()
    app.exec_()
if __name__ == '__main__':
    main()