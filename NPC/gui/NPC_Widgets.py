import platform
op_sys = platform.system()
if op_sys == 'Darwin':
    from Foundation import NSURL
from PyQt4 import QtCore, QtGui
from NPC.gui.ui.npg_ROI_ui import Ui_ROI
from NPC.gui.ui.npg_int_ui import Ui_Intensities
import pyqtgraph as pg
from scipy.ndimage.filters import gaussian_filter
import numpy as np
from PyQt4.QtCore import QPointF as PointF


class ShowROI(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.ui = Ui_ROI()
        self.ui.setupUi(self)

class ShowNumbers(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.ui = Ui_Intensities()
        self.ui.setupUi(self)




class CustomViewBox(pg.ViewBox):
    def __init__(self, parent = None, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)
        self.parent = parent
        self.start = None
        self.roi = None
        self.Roiwin = ShowROI()
        self.Roiwin.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.plotROI = self.Roiwin.ui.graphicsView.addPlot()
        self.ROIviewbox = self.plotROI.getViewBox()
        self.dist_label = []#pg.LabelItem(text='', parent=self.plotROI)

    def addROI(self,start,stop):
        self.roi = pg.LineSegmentROI((start, stop), movable=True, removable=True)

        self.addItem(self.roi)
        self.roi.sigRemoveRequested.connect(self.removeROI)
        self.roi.sigClicked.connect(self.setWinFocus)
        self.roi.sigRegionChanged.connect(self.updatePlot)

    def removeROI(self):
        self.removeItem(self.roi)
        self.roi = None

    def setWinFocus(self):
        if not self.Roiwin.isVisible(): self.Roiwin.show()
        self.Roiwin.setWindowState(self.Roiwin.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        # this will activate the window
        self.Roiwin.activateWindow()

    #def mouseEvent(self, ev):

    def mouseDragEvent(self, ev, axis=None):
        ## if axis is specified, event will only affect that axis.
        ev.accept()  ## we accept all buttons

        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif = dif * -1
        if ev.isStart(): self.roistart = (self.parent.cursorx, self.parent.cursory)

        ## Ignore axes if mouse is disabled
        mouseEnabled = np.array(self.state['mouseEnabled'], dtype=np.float)
        mask = mouseEnabled.copy()
        if axis is not None:
            mask[1-axis] = 0.0

        ## Scale or translate based on mouse button
        if ev.button() & (QtCore.Qt.MidButton | QtCore.Qt.LeftButton):
            if ev.modifiers() == QtCore.Qt.ShiftModifier:
                #if ev.isFinish():
                self.roistop = (self.parent.cursorx, self.parent.cursory)
                if self.roi is not None:
                    self.removeItem(self.roi)
                self.addROI(self.roistart, self.roistop)
                self.updatePlot()


            #if self.state['mouseMode'] == self.RectMode:
            #    if ev.isFinish():  ## This is the final move in the drag; change the view scale now
            #        #print "finish"
            #        self.rbScaleBox.hide()
            #        #ax = QtCore.QRectF(Point(self.pressPos), Point(self.mousePos))
            #        ax = QtCore.QRectF(Point(ev.buttonDownPos(ev.button())), Point(pos))
            #        ax = self.childGroup.mapRectFromParent(ax)
            #        self.showAxRect(ax)
            #        self.axHistoryPointer += 1
            #        self.axHistory = self.axHistory[:self.axHistoryPointer] + [ax]
            #    else:
            #        ## update shape of scale box
            #        self.updateScaleBox(ev.buttonDownPos(), ev.pos())
            else:
                tr = dif*mask
                tr = self.mapToView(tr) - self.mapToView(PointF(0,0))
                x = tr.x() if mask[0] == 1 else None
                y = tr.y() if mask[1] == 1 else None

                self.translateBy(x=x, y=y)
                self.sigRangeChangedManually.emit(self.state['mouseEnabled'])

    def indexes(self, y, thres=0.1, min_dist=5):
        '''Peak detection routine.

        Finds the peaks in *y* by taking its first order difference. By using
        *thres* and *min_dist* parameters, it is possible to reduce the number of
        detected peaks.

        Parameters
        ----------
        y : ndarray
            1D amplitude data to search for peaks.
        thres : float between [0., 1.]
            Normalized threshold. Only the peaks with amplitude higher than the
            threshold will be detected.
        min_dist : int
            Minimum distance between each detected peak. The peak with the highest
            amplitude is preferred to satisfy this constraint.

        Returns
        -------
        ndarray
            Array containing the indexes of the peaks that were detected
        '''
        thres = 1.5 * np.min(y)
        #thres = 0.1 * (np.max(y) - np.min(y))
        # find the peaks by using the first order difference
        dy = np.diff(y)
        peaks = np.where((np.hstack([dy, 0.]) < 0.)
                         & (np.hstack([0., dy]) > 0.)#)[0]
                         & (y > thres))[0]


        if peaks.size > 1 and min_dist > 1:
            highest = peaks[np.argsort(y[peaks])][::-1]
            rem = np.ones(y.size, dtype=bool)
            rem[peaks] = False

            for peak in highest:
                if not rem[peak]:
                    sl = slice(max(0, peak - min_dist), peak + min_dist + 1)
                    rem[sl] = True
                    rem[peak] = False

            peaks = np.arange(y.size)[~rem]

        return peaks

    def updatePlot(self):

        bx = self.parent.bx
        by = self.parent.by
        D = self.parent.distance
        wl = self.parent.wl
        psx = self.parent.psx
        psy = self.parent.psy

        try:
          selected = self.roi.getArrayRegion(self.parent.data, self.parent.img)
        except:
          return
        self.plotROI.plot(selected, clear=True)
        self.setWinFocus()

        if all(x is not None for x in [bx, by, D, wl, psx, psy]):

            filtered = gaussian_filter(selected,2)
            idx = self.indexes(filtered)

            if self.dist_label:
                for label in self.dist_label:
                    self.ROIviewbox.removeItem(label)

            if idx.shape[0] < 2:
                self.dist_label= []#self.dist_label.setText('')
                return

            self.dist_label = [pg.LabelItem(text='', parent=self.plotROI) for i in range(len(idx)-1)]
            for i in range(len(idx)-1):

                # Coordinates of the peak[i]
                alpha = self.roi.angle()
                peak_y = self.roistart[0] + idx[i]* np.sin(alpha * np.pi / 180.)
                peak_x = self.roistart[1] + idx[i]* np.cos(alpha * np.pi / 180.)

                # distance between two peaks (peak[i] and peak[i+1]
                d0 = idx[i+1] - idx[i]
                d = (idx[i+1] - idx[i]) * psx * 1000

                # distance from the  detector center to the first peak
                dcenter = np.sqrt((peak_x-bx)**2+(peak_y-by)**2) * psx *1000
                # distance from the crystal to the peak[i]
                dprime =  np.sqrt(D**2 + dcenter**2)

                # distance in real space
                dist = wl / (2* d / dprime)

                # Calcula label position
                label_x = float(idx[i]+ d0*0.35)
                label_y = float(np.max(selected))/ 2.
                label_pos = QtCore.QPointF(label_x, label_y )
                label_scenepos = self.ROIviewbox.mapViewToScene(label_pos)
                self.dist_label[i].setText('%4.2f'%dist)
                self.dist_label[i].setPos(label_scenepos.x(),label_scenepos.y())


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

