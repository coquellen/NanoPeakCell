import platform
op_sys = platform.system()
if op_sys == 'Darwin':
    from Foundation import NSURL
from PyQt4 import QtGui, QtCore

class TestListView(QtGui.QTreeWidget):
    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        self.setAcceptDrops(True)
        #self.setIconSize(QtCore.QSize(72, 72))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()


    def dropEvent(self, event):
        if event.mimeData().hasUrls:

            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                if op_sys == 'Darwin':
                    fname = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path())
                else:
                    fname = str(url.toLocalFile())

                links.append(fname)
            self.emit(QtCore.SIGNAL("dropped"), links)

        else:
            event.ignore()

