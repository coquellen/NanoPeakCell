import numpy as np, h5py
import pyFAI
import pyqtgraph as pg
import zmq
from NPC.gui.NPC_Widgets import CustomViewBox, ShowNumbers
from NPC.utils import get_class, parseHits
from pyqtgraph import functions as fn
from pyqtgraph.graphicsItems.ROI import Handle as pgHandle
from NPC.gui.Frame import TreeFactory
from NPC.gui.ui import MainWindow_NoMenu_ui as MainWindow_ui, FileTree_ui, XP_Params_ui, HitFinding_ui, LiveHF, Runs_ui, Geom_ui

try:
    from PyQt5 import QtGui, QtCore
    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtGui import QMainWindow, QWidget, QIcon, QColor, QFileDialog, QCloseEvent
except:
    from PyQt4 import QtGui, QtCore
    from PyQt4.QtCore import pyqtSignal
    from PyQt4.QtGui import QMainWindow, QWidget, QIcon, QColor, QFileDialog, QCloseEvent

import os, json, time
import pkg_resources as pkg
from datetime import datetime


pg.setConfigOptions(imageAxisOrder='row-major')

colorHoverMapping = [(255, 255, 0),
                     (255, 255, 0),
                     (0, 0, 255),
                     (255, 0, 0),
                     (255, 255, 255),
                     (0, 0, 0),
                     (255, 255, 255),
                     (255, 255, 255),
                     (255, 255, 255),
                     (0, 0, 0)
                     ]


def Log(message):

    message = time.strftime("[%H:%M:%S]:  ") + message
    return message


class BeamCenter(pg.QtGui.QGraphicsEllipseItem):

    def __init__(self, brush):
        super(BeamCenter, self).__init__(0, 0, 0, 0)
        self.hide()
        self.brush = brush
        self.setBrush(self.brush)

    def setPos(self, bx, by, binning):
        posX = (float(bx) - 20) / binning
        posY = (float(by) - 20) / binning
        size = 40. / binning
        self.setRect(posX, posY, size, size)


class ResolutionRing(pg.QtGui.QGraphicsEllipseItem):

    def __init__(self, pen):
        super(ResolutionRing, self).__init__(0, 0, 0, 0)
        self.hide()
        self.pen = pen
        self.setPen(self.pen)


class NPGTextItem(pg.TextItem):

    def __init__(self, text, anchor):
        super(NPGTextItem, self).__init__(text=text, anchor=anchor)


    def setColor(self, color):
        """
        Set the color for this text.

        See QtGui.QGraphicsItem.setDefaultTextColor().
        """
        self.color = fn.mkColor(color)
        self.textItem.setDefaultTextColor(self.color)


class ResolutionTxt(NPGTextItem):
    def __init__(self, color):
        super(ResolutionTxt, self).__init__( "", anchor=(0.5, 0))
        self.color = color
        self.hide()
        self.setPos(0, 0)
        self.setColor(self.color)


class Handle(pgHandle):

    def __init__(self, radius, typ=None, pen=(200, 200, 220), parent=None, deletable=False):
        super(Handle, self).__init__(radius, typ, pen, parent, deletable)
        self.hoverColor = colorHoverMapping[0]
        self.pen.setWidth(4)

    def mouseDragEvent(self, ev):
        if ev.button() != QtCore.Qt.LeftButton:
            return
        ev.accept()

        ## Inform ROIs that a drag is happening
        ##  note: the ROI is informed that the handle has moved using ROI.movePoint
        ##  this is for other (more nefarious) purposes.
        # for r in self.roi:
        # r[0].pointDragEvent(r[1], ev)
        if ev.isFinish():
            if self.isMoving:
                for r in self.rois:
                    r.stateChangeFinished()
            self.isMoving = False
            self.currentPen = self.pen
        elif ev.isStart():
            for r in self.rois:
                r.handleMoveStarted()
            self.isMoving = True
            self.startPos = self.scenePos()
            self.cursorOffset = self.scenePos() - ev.buttonDownScenePos()

        if self.isMoving:  ## note: isMoving may become False in mid-drag due to right-click.
            pos = ev.scenePos() + self.cursorOffset
            self.movePoint(pos, ev.modifiers(), finish=False)
            r, g, b = self.hoverColor
            self.currentPen = fn.mkPen(r, g, b, width=6)

    def hoverEvent(self, ev):
        hover = False
        if not ev.isExit():
            if ev.acceptDrags(QtCore.Qt.LeftButton):
                hover = True
            for btn in [QtCore.Qt.LeftButton, QtCore.Qt.RightButton, QtCore.Qt.MidButton]:
                if int(self.acceptedMouseButtons() & btn) > 0 and ev.acceptClicks(btn):
                    hover = True

        if hover:
            r, g, b = self.hoverColor
            self.currentPen = fn.mkPen(r, g, b, width=6)
        else:
            self.currentPen = self.pen
        self.update()


class RectROI(pg.ROI):
    """
    Rectangular ROI subclass with a single scale handle at the top-right corner.

    ============== =============================================================
    **Arguments**
    pos            (length-2 sequence) The position of the ROI origin.
                   See ROI().
    size           (length-2 sequence) The size of the ROI. See ROI().
    centered       (bool) If True, scale handles affect the ROI relative to its
                   center, rather than its origin.
    sideScalers    (bool) If True, extra scale handles are added at the top and
                   right edges.
    \**args        All extra keyword arguments are passed to ROI()
    ============== =============================================================

    """

    sigDragFinished = pyqtSignal(tuple)

    def __init__(self, centered=False, sideScalers=False, binning=1., **args):
        # QtGui.QGraphicsRectItem.__init__(self, 0, 0, size[0], size[1])
        self.binning = binning
        self.roistartX = 0
        self.roistartY = 0
        self.roistopX = 1000
        self.roistopY = 1000
        self.roistart = (self.roistartX / self.binning, self.roistartY / self.binning)
        self.roistop = (self.roistopX / self.binning, self.roistopY / self.binning)
        self.roisize = (self.roistop[0] - self.roistart[0], self.roistop[1] - self.roistart[1])
        pg.ROI.__init__(self, self.roistart, self.roisize, **args)
        if centered:
            center = [0.5, 0.5]
        else:
            center = [0, 1]
        self.addScaleHandle([1, 0], center)
        self.count = 0
        self.hoverColor = colorHoverMapping[0]
        self.handle = self.handles[0]['item']

        self.sigRegionChangeFinished.connect(self.roiDragFinished)

    def updateVisible(self):
        if self.isVisible():
            self.setVisible(False)
        else:
            self.setVisible(True)

    def roiDragFinished(self):
        """
        This function get the position and size of the roi once
        the re-sizing / re-positiong is done.
        It takes the binning into account.
        It sends the roi positions to the gui"""
        x, y = self.pos()
        w, h = self.size()
        X = x * self.binning
        Y = y * self.binning
        W = X + w * self.binning
        H = Y + h * self.binning
        self.sigDragFinished.emit((X,Y,W,H))

    def setPosNSize(self, roi):
        x1, y1 , x2, y2 = roi
        self.roistartX = x1 / self.binning
        self.roistartY = y1 / self.binning
        self.roistopX  = x2 / self.binning
        self.roistopY  = y2 / self.binning
        self.roistart = (self.roistartX, self.roistartY)
        self.roistop = (self.roistopX,  self.roistopY)
        self.setPos(self.roistart, finish=False)
        size = (self.roistop[0] - self.roistart[0], self.roistop[1] - self.roistart[1])
        self.setSize(size, finish=False)

    def addHandle(self, info, index=None):
        ## If a Handle was not supplied, create it now
        if 'item' not in info or info['item'] is None:
            h = Handle(self.handleSize, typ=info['type'], pen=self.handlePen, parent=self)
            h.setPos(info['pos'] * self.state['size'])
            info['item'] = h
        else:
            h = info['item']
            if info['pos'] is None:
                info['pos'] = h.pos()
                ## connect the handle to this ROI
                # iid = len(self.handles)

        h.connectROI(self)
        if index is None:
            self.handles.append(info)
        else:
            self.handles.insert(index, info)

        h.setZValue(self.zValue() + 1)
        self.stateChanged()
        return h

    def mouseDragEvent(self, ev):
        if ev.isStart():
            # p = ev.pos()
            # if not self.isMoving and not self.shape().contains(p):
            # ev.ignore()
            # return
            if ev.button() == QtCore.Qt.LeftButton:
                self.setSelected(True)
                if self.translatable:
                    self.isMoving = True
                    self.currentPen = self._makePen()
                    self.update()
                    self.preMoveState = self.getState()
                    self.cursorOffset = self.pos() - self.mapToParent(ev.buttonDownPos())
                    self.sigRegionChangeStarted.emit(self)
                    ev.accept()
                else:
                    ev.ignore()

        elif ev.isFinish():
            if self.translatable:
                if self.isMoving:
                    self.stateChangeFinished()
                self.isMoving = False
                self.currentPen = self._makePen()
                self.update()
            return

        if self.translatable and self.isMoving and ev.buttons() == QtCore.Qt.LeftButton:
            snap = True if (ev.modifiers() & QtCore.Qt.ControlModifier) else None
            newPos = self.mapToParent(ev.pos()) + self.cursorOffset
            self.translate(newPos - self.pos(), snap=snap, finish=False)

    def _makePen(self):
        # Generate the pen color for this ROI based on its current state.
        if self.mouseHovering or self.isMoving:
            r, g, b = self.hoverColor
            return fn.mkPen(r, g, b, width=4)
        else:
            return self.pen


class NPGViewBox(CustomViewBox):

    color_mapping =  [(255, 255, 255),
                      (255, 0, 0),
                      (0, 0, 0),
                      (0, 0, 0),
                      (255, 255, 255),
                      (0, 0, 0),
                      (255, 255, 255),
                      (255, 255, 255),
                      (255, 255, 255),
                      (0, 0, 0)
                      ]


    def __init__(self, parent, binning,nRings=4):
        super(NPGViewBox, self).__init__(parent, invertY=True)
        self.parent = parent
        self.color = self.color_mapping[0]
        self.binning = binning
        self.nRings = nRings
        self.vmin = 0
        self.vmax = 10
        self.pen = pg.mkPen(self.color, width=2, style=QtCore.Qt.SolidLine)
        self.emptyBrush = pg.mkBrush(None)
        self.filledBrush = pg.mkBrush(self.color)


        # Setting our view items - One Imageitem and two ScatterPlotItems
        self.setAspectLocked()
        self.img = pg.ImageItem()
        self.addItem(self.img)
        self.DetectedPlot =  pg.ScatterPlotItem(pen=self.pen, brush=self.emptyBrush, pxMode=False)
        self.IntegratedPlot = pg.ScatterPlotItem(pen=self.pen, brush=self.emptyBrush, pxMode=False)
        self.addItem(self.DetectedPlot)
        self.addItem(self.IntegratedPlot)

        self.beam = BeamCenter(self.filledBrush)
        self.addItem(self.beam)
        self.rings = [ResolutionRing(self.pen) for i in range(nRings)]
        self.ringsTxt = [ResolutionTxt(self.color) for i in range(nRings)]
        for i in range(nRings):
            self.addItem(self.rings[i])
            self.addItem(self.ringsTxt[i])

        self.roi = RectROI(movable=True,
                           removable=False,
                           pen={'color': "FF0", 'width': 4}, binning= self.binning)
        self.roi.hide()
        self.addItem(self.roi)
        # TODO: Change to the pkg path (see old npg)
        self.cmaps = [np.load(pkg.resource_filename('NPC','gui/cmaps/%s.npy'%self.parent.ui.ColorMap.itemText(i))) for i in range(self.parent.ui.ColorMap.count())]
        #self.autoRange(items=[self.img])

    def resetZoom(self):
        self.autoRange(items=[self.img])

    def updateCmap(self):
        idx = int(self.parent.ui.ColorMap.currentIndex())
        self.cmap = self.cmaps[idx]
        self.img.setLookupTable(self.cmap)
        R, G, B = self.color_mapping[idx]
        self.QColor = QColor(R, G, B)
        self.pen.setColor(self.QColor)
        self.filledBrush.setColor(self.QColor)
        self.beam.setBrush(self.filledBrush)
        self.roi.setPen(self.pen)
        self.roi.hoverColor = colorHoverMapping[idx]
        self.roi.handle.currentPen = self.pen
        self.roi.handle.pen = self.pen
        self.roi.handle.hoverColor = colorHoverMapping[idx]
        self.roi.handle.update()

        for i in range(self.nRings):
            self.rings[i].setPen(self.pen)
            self.ringsTxt[i].setColor(self.QColor)


class NPGWidget(QWidget):

    hideMe = pyqtSignal(str)
    visible = True
    raiseAll = pyqtSignal(str)

    def __init__(self, name):
        QWidget.__init__(self)
        #self.mouse = False
        #self.name = name

    def closeEvent(self, QCloseEvent):
        self.closeSignal.emit(QCloseEvent)
        self.Pos = self.pos()
        self.close()

    #def enterEvent(self, QEvent):
    #print("Mouse entered")
    #    self.mouse = True

    #def leaveEvent(self, QEvent):
    #print("Mouse Leaved")
    #    self.mouse = False

    #def changeEvent(self, QEvent):
    #    if self.mouse:
    #        self.raiseAll.emit(self.name)


class ImageView(QMainWindow):

    closeSignal = pyqtSignal(QCloseEvent)
    raiseAll = pyqtSignal(str)
    visible = True


    def __init__(self, XPView, binning, name,nRings=4):
        super(ImageView, self).__init__()
        self.ui = MainWindow_ui.Ui_MainWindow()
        self.name = name
        self.ui.setupUi(self)
        self.nRings = nRings
        self.ui.Stream.hide()
        self.XPView = XPView
        self.binning = binning
        self.vmin = 0
        self.vmax = 10
        self.showBragg = False
        self.popup_int = ShowNumbers()
        self.show()
        self.raise_()


        # Setting up our ImageItem for pyqtgraph
        self.view = NPGViewBox(parent=self, binning= self.binning, nRings=self.nRings)
        self.ui.graphicsView.setCentralItem(self.view)

        #These bindings are not in the controller as they immediately change the view
        self.ui.Max.editingFinished.connect(self.setLevels)
        self.ui.Min.editingFinished.connect(self.setLevels)
        self.ui.ColorMap.currentIndexChanged.connect(self.view.updateCmap)
        self.ui.Reset.clicked.connect(self.view.resetZoom)

        self.XPView.ui.beamX.editingFinished.connect(self.setBeam)#
        self.XPView.ui.beamY.editingFinished.connect(self.setBeam)
        self.XPView.ui.distance.editingFinished.connect(self.setDistance)
        self.XPView.ui.Wavelength.editingFinished.connect(self.setWavelength)
        self.XPView.ui.Detector.currentIndexChanged.connect(self.setDetector)

        self.proxy = pg.SignalProxy(self.view.scene().sigMouseMoved, rateLimit=30, slot=self.mouseMoved)

    def setAttr(self):
        try:
            self.vmax = int(self.ui.Max.text())
            self.vmin = int(self.ui.Min.text())
        except:
            self.vmin = 0
            self.vmax = 10
        self.view.updateCmap()

    def setImg(self, data):
        self.shape = data.shape
        if self.binning != 1:
            self.data = self.rebin(data)
        else: self.data = data
        self.view.img.setImage(self.data.astype(np.float64), levels=(self.vmin, self.vmax))
        if self.showBragg :
            self.view.IntegratedPlot.setData([],[])
            self.showBragg = False

    def setLevels(self):
        try:
            self.vmax = int(self.ui.Max.text())
            self.vmin = int(self.ui.Min.text())
            self.view.img.setLevels((self.vmin, self.vmax))
        except ValueError:
            print('Integer expected for the maximum cmap value... Try Again.')

    def setBeam(self):
        self.XPView.getBeam()
        print("New beam center position: X = %5i -- Y = %5i" % (self.XPView.bx, self.XPView.by))
        self.view.beam.setPos(self.XPView.bx, self.XPView.by, self.binning)
        self.setResRingsPosition()

    def setDistance(self):
        self.XPView.getDistance()
        print("New detector distance (mm): %4.2f " % (self.XPView.distance))
        self.setResRingsPosition()

    def setWavelength(self):
        self.XPView.getWavelength()
        self.setResRingsPosition()

    def setDetector(self):
        self.XPView.getDetector()
        self.setResRingsPosition()
        self.ymax, self.xmax = self.XPView.detector.shape
        if self.binning == 1:
            self.Imin = 0
            self.Imax = 1
        else:
            self.Imin = self.binning
            self.Imax = self.binning + 1

    def setResRingsPosition(self):
        self.view.beam.setPos(self.XPView.bx, self.XPView.by, self.binning)
        try:
            max_radius = max(self.shape[1] - self.XPView.bx,
                             self.shape[0] - self.XPView.by,
                             self.shape[0] - self.XPView.bx,
                             self.shape[1] - self.XPView.by,
                             self.XPView.bx,
                             self.XPView.by)
            increment = max_radius / (float(self.nRings) * self.binning)
            for i in range(self.nRings):
                radius = increment * (i + 1)
                x = float(self.XPView.bx / self.binning) - radius
                y = float(self.XPView.by / self.binning) - radius
                self.view.rings[i].setRect(x, y, radius * 2, radius * 2)
                resolution = "%4.1f A" % float(self.getResolution(self.XPView.bx, self.XPView.by - radius * self.binning))

                self.view.ringsTxt[i].setPos(x + radius, y)
                self.view.ringsTxt[i].setText(resolution)
            return True
        except AttributeError:
            return False

    def getResolution(self, x, y):
        try:
            dx = x - self.XPView.bx
            dy = y - self.XPView.by
            dx *= self.XPView.psx
            dy *= self.XPView.psy
            radius = np.sqrt(dx ** 2 + dy ** 2)
            theta = 0.5 * np.arctan(radius / (self.XPView.distance / 1000))
            return '%4.2f ' % (self.XPView.wl / (2. * np.sin(theta)))
        except:
            return 'nan'

    def mousePressEvent(self, QMouseEvent):
        if QMouseEvent.button() == QtCore.Qt.MidButton and self.view.sceneBoundingRect().contains(QMouseEvent.pos()):
                x = self.cursorx
                y = self.cursory
            #try:
                xmax, ymax = self.data.shape
                if self.cursorx > 0 and self.cursory > 0 and self.cursorx < xmax and self.cursory < ymax:
                    data = self.data[y - 10:y + 9, x - 10:x + 9]
                    s = ''
                    for i in range(0, 19):
                      s = s + '\n' + ''.join(['%6i' % member for member in data[i, :]])
                    self.popup_int.ui.textEdit.setText("%s" % s)
                    if not self.popup_int.isVisible(): self.popup_int.show()
                    self.popup_int.setWindowState(
                        self.popup_int.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
                    # this will activate the window
                    self.popup_int.activateWindow()
            #except AttributeError:
                #print('No data loaded yet')

    def updateBoost(self):
        #try:
        #    self.boost = int(self.ui.Boost.text())
        #    self.img.setImage(self.data ** self.boost)
        #    self.img.setLevels((self.vmin, self.vmax))
        #except ValueError:
        #    print('Integer expected for the boost value... Try Again.')
        pass

    def rebin(self, data):
        """
        Rebin the data and adjust dims
        @param x_rebin_fact: x binning factor
        @param y_rebin_fact: y binning factor
        @param keep_I: shall the signal increase ?
        @type x_rebin_fact: int
        @type y_rebin_fact: int
        """
        shapeIn = data.shape
        dim1Out = shapeIn[0] // self.binning
        dim2Out = shapeIn[1] // self.binning


        temp = data[0:dim1Out * self.binning, 0:dim2Out * self.binning].astype("float32")
        temp.shape = (dim1Out, self.binning, dim2Out, self.binning)
        return temp.max(axis=3).max(axis=1).astype(data.dtype)
        #return out.astype(data.dtype)

    def mouseMoved(self, evt):

        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        if self.view.sceneBoundingRect().contains(pos):
            mousePoint = self.view.mapSceneToView(pos)
            self.cursorx = int(mousePoint.x()) #* self.binning
            self.cursory = int(mousePoint.y()) #* self.binning
            #print("Mouse Moved", self.cursorx, self.cursory)
            try:
                #TODO: Modify when model implemented

                if self.cursorx > 0 and self.cursory > 0 and self.cursorx < self.xmax and self.cursory < self.ymax:
                    try:
                        #I = self.data[self.cursorx, self.cursory]
                        I = self.data[self.cursory, self.cursorx]
                    except:
                       I = 0
                    res = self.getResolution(self.cursorx * self.binning, self.cursory * self.binning)
                    self.ui.ImageInfo.setText("x: %4i - y: %4i    -- Res: %7s  -- I: %4i" % (self.cursorx * self.binning,
                                                                                             self.cursory * self.binning,
                                                                                             res,
                                                                                             I))

            except AttributeError:
                pass

    def toggleBeamCenter(self):
        if self.view.beam.isVisible():
            self.view.beam.hide()
            return True
        else:
            if hasattr(self.data, 'shape'):
                self.view.beam.setPos(self.XPView.bx, self.XPView.by, self.binning)
                self.view.beam.show()
                return True
            else:
                print("No data loaded")
                return False

    def toggleResRings(self):
        if self.setResRingsPosition():
            if self.view.rings[0].isVisible():
                for r in self.view.rings: r.hide()
                for txt in self.view.ringsTxt: txt.hide()
            else:
                for r in self.view.rings: r.show()
                for txt in self.view.ringsTxt: txt.show()
            return True

        else:
            return False

    def updateStreamWidgetState(self):
        if self.ui.Stream.isVisible():
            self.ui.Stream.show()

    def closeEvent(self, QCloseEvent):
        self.closeSignal.emit(QCloseEvent)
        self.Pos = self.pos()
        self.close()


class ImageViewOnline(ImageView):

    def __init__(self, XPView, binning, name, zmqSocket, req, timeout):
        super(ImageViewOnline, self).__init__(XPView, binning, name)

        self.zmqSocket = zmqSocket
        self.request = req
        self.timeout = timeout
        self.sendReq = True

        self.imgTimer = QtCore.QTimer()
        self.imgTimer.timeout.connect(self.sendRequest)
        self.imgTimer.start(timeout)

    def proc(self, data):
        self.setImg(data)

    def sendRequest(self):
        self.zmqSocket.send(self.request)

        try:
            md = self.zmqSocket.recv_json(zmq.NOBLOCK)
            data = self.zmqSocket.recv(copy=False, track=False)
            buf = buffer(data)
            A = np.frombuffer(buf, dtype=md['dtype']).reshape(md['shape'])
            self.proc(A)
            #self.sendReq = True

        except:
            tmp = self.zmqSocket.recv()
            #print tmp


class MaxProjViewOnline(ImageViewOnline):


    visible = True
    hideMe = pyqtSignal(str)
    sigResetMP = pyqtSignal()

    def __init__(self, XPView, binning, name, zmqSocket, req, timeout):
        super(MaxProjViewOnline, self).__init__(XPView, binning, name, zmqSocket, req, timeout)


        ###Adding some extra widgets
        self.ui.layoutWidget.setGeometry(QtCore.QRect(10, 30, 209, 211))
        self.ui.groupBox.setMinimumSize(QtCore.QSize(220, 260))
        self.ui.groupBox.setMaximumSize(QtCore.QSize(220, 260))
        self.ui.ResetMP = QtGui.QPushButton(self.ui.layoutWidget)
        self.ui.ResetMP.setObjectName("ResetMP")
        self.ui.ResetMP.setText("Reset Max Proj")
        self.ui.verticalLayout.addWidget(self.ui.ResetMP)
        self.ui.ResetMP.clicked.connect(self.resetMP)
        self.ui.SaveMP = QtGui.QPushButton(self.ui.layoutWidget)
        self.ui.SaveMP.setObjectName("SaveMP")
        self.ui.SaveMP.setText("Save Max Proj")
        self.ui.verticalLayout.addWidget(self.ui.SaveMP)
        self.ui.SaveMP.clicked.connect(self.saveMP)


    def __init_shape__(self, shape):
        self.shape = shape
        self.MP = np.zeros(self.shape)

    def sendRequest(self):
        self.zmqSocket.send(self.request)
        md = self.zmqSocket.recv_json()
        data = self.zmqSocket.recv(copy=False, track=False)
        buf = buffer(data)
        A = np.frombuffer(buf, dtype=md['dtype']).reshape(md['shape'])
        self.proc(A)


    def proc(self, data):
        self.setImg(data)

    def resetMP(self):
        self.MP = np.zeros(self.shape)
        self.setImg(self.MP)
        self.saveMP()
        self.sigResetMP.emit()


    def saveMP(self):
        now = datetime.today()
        fn = 'MaxProj-%s.h5' % (now.strftime('%Y-%m-%d-%H-%M-%S'))
        h5 = h5py.File(fn, 'w')
        h5.create_dataset("data", data=self.MP)
        h5.close()

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionMaximum_Projection')
            self.Pos = self.pos()

        else:
            self.saveMP()
            self.close()


class XPView(NPGWidget):

    name = 'XPView'

    def __init__(self, Live):
        super(XPView, self).__init__(name=self.name)
        self.wl = 0
        self.distance  = 0
        self.bx = 0
        self.by = 0
        self.d = 0
        self.ui = XP_Params_ui.Ui_Form()
        self.ui.setupUi(self, Live)
        self.show()

    def setupData(self):
        self.getDetector()
        self.getBeam()
        self.getDistance()
        self.getWavelength()

    def getWavelength(self):
        try:
            self.wl = float(self.ui.Wavelength.text())
        except ValueError:
            print('Float expected for the wavelength... Try Again.')
            self.ui.Wavelength.setText(str(self.wl))

    def getDistance(self):
        try:
            self.distance = float(self.ui.distance.text())
        except ValueError:
            print('Float expected for the distance... Try Again.')
            self.ui.distance.setText(str(self.d))

    def getBeam(self):
        try:
            self.bx = float(self.ui.beamX.text())
            self.by = float(self.ui.beamY.text())
        except ValueError:
            print('Floats (or int...) expected for the beam center')
            self.ui.beamX.setText(str(self.bx))
            self.ui.beamY.setText(str(self.by))

    def getDetector(self,verbose=False):
        det = self.ui.Detector.currentText()
        try:
            self.detector = pyFAI.detector_factory(str(det))
        except:
            self.detector = get_class("NPC.Detectors", str(det))()
        self.psx = self.detector.pixel1
        self.psy = self.detector.pixel2
        if verbose: Log("Detector updated to %s" % str(det))

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionExperimental_Settings')
            self.Pos = self.pos()
        else:
            self.close()

    def readHeader(self, header):
        #print("This is it")
        from .Headers import readheader
        try:
            self.distance, self.psx, self.psy, self.wl, self.bx, self.by, det = readheader(header)
            self.detector = pyFAI.detector_factory(str(det))
            self.ui.beamX.setText(str(self.bx))
            self.ui.beamY.setText(str(self.by))
            self.ui.distance.setText((str(self.distance)))
            self.ui.Wavelength.setText(str(self.wl))
            index = self.ui.Detector.findText(det)
            self.ui.Detector.setCurrentIndex(index)
        except:
            pass

class CsPADGeom(NPGWidget):

    name = 'CsPADGeom'

    def __init__(self):
        super(CsPADGeom, self).__init__(name=self.name)
        self.ui = Geom_ui.Ui_QuadControl()
        self.ui.setupUi(self)
        self.show()


    def getQuadrantStatus(self):
        q0 = self.ui.Quadrant0.isChecked()
        q1 = self.ui.Quadrant1.isChecked()
        q2 = self.ui.Quadrant2.isChecked()
        q3 = self.ui.Quadrant3.isChecked()

        return [q0,q1,q2,q3]

    def getIncrement(self):
        try:
            inc = int(self.ui.lineEdit.text())
            return inc
        except ValueError:
            print("The increment should be an integer")
            return

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionCsPADGeom')
            self.Pos = self.pos()
        else:
            self.close()


class TreeFileView(NPGWidget):

    openFile = pyqtSignal(tuple)
    name = 'TreeFileView'
    #dropped = QtCore.pyqtSignal(list)



    def __init__(self, parent=None):
        super(TreeFileView, self).__init__(name=self.name)
        self.ui = FileTree_ui.Ui_Form()
        self.ui.setupUi(self)
        self.show()
        self.treeFactory = TreeFactory(self.ui.treeWidget)
        self.treeItem = None
        self.count = 0
        self.playtimer = QtCore.QTimer()
        self.playtimer.timeout.connect(self.updateData)
        self.showIndexed = False

        self.ui.treeWidget.dropped.connect(self.objectDropped)
        self.ui.treeWidget.itemSelectionChanged.connect(self.updateTree)

    def objectDropped(self, l):
        #print l, type(l)
        for url in l:
            if os.path.exists(url):
                self.treeFactory.append_object(url)

    def updateTree(self):
        self.treeItem = self.ui.treeWidget.currentItem()
        # N is the number of images containes in a file
        N = str(self.treeItem.text(1))
        # 'tba' is used to avoid visiting all h5 during tree construction
        if N == 'tba':

            self.treeFactory.construct_tree_h5(str(self.treeItem.text(0)), self.treeItem)
            if str(self.treeItem.text(1)) == '1':
                self.updateFilename()
        elif int(self.treeItem.childCount()) != 0:
            return
        else:
            self.updateFilename()

    def updateFilename(self):
        # Functional - but would need quite some rewriting

        if self.treeItem == None:
            self.treeItem = self.ui.treeWidget.currentItem()

        field = str(self.treeItem.text(0))
        if field in self.treeFactory.filenames_dic.keys():
            fn = self.treeFactory.filenames_dic[field]
            if os.path.exists(fn):
                if fn in self.treeFactory.h5_dic.keys():
                    path, shape = self.treeFactory.h5_dic[fn][0]
                    self.openFile.emit((fn, path, None))
                else:
                    self.openFile.emit((fn, None, None))

        else:
            try:
                path, index = str(self.treeItem.text(0)).split()
                parent = self.treeItem.parent()
                fn = self.treeFactory.filenames_dic[str(parent.text(0))]
                if not os.path.isfile(fn):
                    parent2 = parent.parent()
                    fn = self.treeFactory.filenames_dic[str(parent2.text(0))]
                self.openFile.emit((str(fn), path, int(index)))
            except ValueError:
                return

    #def dropEvent(self, event):
    #    print event.mimeData().text()
        #self.dropped.emit(list_of_files)


    def play(self):
        self.idx = 0
        self.treeItem = self.ui.treeWidget.currentItem()
        self.playtimer.start(500)

    def stop(self):
        self.ui.treeWidget.setCurrentItem(self.treeItem)
        self.playtimer.stop()

    def updateData(self):

        item = self.ui.treeWidget.itemBelow(self.treeItem)

        if item is not None:
            self.treeItem = item
            if self.count % 10 == 0:
                self.ui.treeWidget.setCurrentItem(item)
            self.updateFilename()
            self.count += 1
        else:
            self.stop()

    def clearTree(self):
        self.ui.treeWidget.clear()
        # This could be save for reused (especially for h5)
        #
        self.treeFactory.filenames_dic = {}
        self.treeFactory.h5_dic = {}

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionFile_Tree')
            self.Pos = self.pos()
        else:
            self.close()

    def testing(self, fns, clear=False):
        if self.showIndexed:
            self.treeFactory.hits = parseHits(fns[1], openfn=False)
        else:
            self.treeFactory.hits = parseHits(fns[0], openfn=False)

        self.treeFactory.run_hits(self.treeFactory.hits, clear=clear)


class NPGprogressBar(QtGui.QProgressBar):

    def __init__(self):
        QtGui.QProgressBar.__init__(self)
        self.setTextVisible(False)
        self.layout = QtGui.QHBoxLayout(self)
        self.overlay = QtGui.QLabel()
        self.overlay.setAlignment(QtCore.Qt.AlignCenter)
        self.overlay.setText("")
        self.layout.addWidget(self.overlay)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def setValueAndText(self, p_int):
        self.setValue(int(p_int))
        self.overlay.setText("%4.2f" % float(p_int))


class TableWidget(NPGWidget):

    loadResults = QtCore.pyqtSignal(str)
    deleteFolder = QtCore.pyqtSignal(str)
    stop = QtCore.pyqtSignal(int)
    name = 'Table'

    def __init__(self):
        super(TableWidget, self).__init__(name= self.name)
        self.ui = Runs_ui.Ui_Form()
        self.ui.setupUi(self)
        self.currentRow = 0
        self.font = QtGui.QFont()
        self.font.setFamily('.NS FS Text')
        self.font.setPointSize(11)
        # Debug
        #self.show()

    def addRow(self, run, Done = True):
        self.ui.tableWidget.insertRow(self.currentRow)
        self.addVerticalHeader(run)

        Nevents = self.addItem()
        Nhits = self.addItem()
        hitRate = self.addItem()
        resultsButton = self.addPushButton(label='Load Hits', icon=None)
        deleteButton = self.addPushButton("", icon=pkg.resource_filename('NPC','gui/icons/waste-bin.svg'))
        if Done:
            pBar = self.addItem()
            self.ui.tableWidget.setItem(self.currentRow, 3, pBar)
            stopButton = self.addPushButton("", icon=pkg.resource_filename('NPC','gui/icons/Delete.png'), enabled=False)

        else:
            pBar = NPGprogressBar()
            self.ui.tableWidget.setCellWidget(self.currentRow, 3, pBar)
            resultsButton.setDisabled(True)
            stopButton = self.addPushButton("", icon=pkg.resource_filename('NPC','gui/icons/Delete.png'), enabled=False)

        self.ui.tableWidget.setItem(self.currentRow, 0, Nevents)
        self.ui.tableWidget.setItem(self.currentRow, 1, Nhits)
        self.ui.tableWidget.setItem(self.currentRow, 2, hitRate)
        self.ui.tableWidget.setCellWidget(self.currentRow, 4, stopButton)
        self.ui.tableWidget.setCellWidget(self.currentRow, 5, resultsButton)
        self.ui.tableWidget.setCellWidget(self.currentRow, 6, deleteButton)

        resultsButton.clicked.connect(lambda: self.emitNPCRun(Nevents))
        stopButton.clicked.connect(lambda: self.emitStop(Nevents))
        deleteButton.clicked.connect(lambda : self.deleteRow(Nevents))

        if Done: self.setDoneRow(self.currentRow)

        self.currentRow += 1

    def addVerticalHeader(self, run):
        item = QtGui.QTableWidgetItem()
        item.setText("Run #%s" % str(run).zfill(3))
        self.ui.tableWidget.setVerticalHeaderItem(self.currentRow, item)

    def setDoneRow(self, row):
        self.Nevents = self.ui.tableWidget.item(row, 0)
        self.Nhits = self.ui.tableWidget.item(row, 1)
        self.hitRate = self.ui.tableWidget.item(row, 2)
        self.pBar = self.ui.tableWidget.item(row, 3)
        self.stopButton = self.ui.tableWidget.cellWidget(row, 4)
        self.Results = self.ui.tableWidget.cellWidget(row, 5)
        self.Delete = self.ui.tableWidget.cellWidget(row, 6)

    def setActiveRow(self, row):
        self.Nevents = self.ui.tableWidget.item(row, 0)
        self.Nhits = self.ui.tableWidget.item(row, 1)
        self.hitRate = self.ui.tableWidget.item(row, 2)
        self.pBar = self.ui.tableWidget.cellWidget(row, 3)
        self.stopButton = self.ui.tableWidget.cellWidget(row, 4)
        self.Results = self.ui.tableWidget.cellWidget(row, 5)
        self.Delete = self.ui.tableWidget.cellWidget(row, 6)

    def addItem(self):
        item = QtGui.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter)
        return item


    def addPushButton(self, label, icon=None, enabled=True):
        item = QtGui.QPushButton(label)
        item.setEnabled(enabled)
        item.setFont(self.font)
        if icon is not None:
            item.setIcon(QtGui.QIcon(icon))
            item.setIconSize(QtCore.QSize(16, 16))
        return item

    def deleteRow(self, item):
        row, run = self.getRunNumber(item)
        self.ui.tableWidget.removeRow(row)
        self.deleteFolder.emit(run)
        self.currentRow -= 1

    def emitNPCRun(self, item):
        _, run = self.getRunNumber(item)
        self.loadResults.emit(run)

    def emitStop(self, item):
        row, run = self.getRunNumber(item)
        self.stop.emit(row)

    def getRunNumber(self, item):
        row = self.ui.tableWidget.row(item)
        Header = self.ui.tableWidget.verticalHeaderItem(row)
        run = str(Header.text())[-3:]
        return row, run

    def progress(self, data):
        Total, N, hit = data
        self.Nevents.setText("%8i" % N)
        self.Nhits.setText("%8i" % hit)
        if N> 0:
            self.hitRate.setText("%4.2f" % (float(hit) / N * 100))
        else: self.hitRate.setText("0.00")
        if Total > 0:
            self.pBar.setValueAndText(float(N) / Total * 100)

    def restoreRows(self, dirs):
        self.ui.tableWidget.setRowCount(0)
        self.currentRow = 0
        nRun = 0
        nRow = 0
        for d in dirs:
            nRun = int(d[-3:])
            self.addRow(nRun)
            print nRun
            print self.Nevents
            try:
                options = json.loads(open(os.path.join(d, ".NPC_params.json")).read())
                nRun = int(options['num'])

                self.Nevents.setText("%6i" % options['processed'])
                self.Nhits.setText("%6i" % options['hit'])
                N = options['processed']  # except IOError:
                if N > 0:
                    self.hitRate.setText("%4.2f" % (options['hit'] / float(options['processed']) * 100))
                    self.pBar.setText("Finished (%4.2f)" % (options['processed'] / float(options['total']) * 100))
                else:
                    self.hitRate.setText("%4.2f" % (0))
                    self.pBar.setText("No event processed")
                nRow += 1
            except IOError:
                self.Nevents.setText("--")
                self.Nhits.setText("--")
                self.hitRate.setText("--")
                self.pBar.setText("N/A")

            except AttributeError:
                pass


        return nRun, nRow

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionRuns')
            self.Pos = self.pos()
        else:
            self.close()


class HitFindingView(NPGWidget):

    setTable = pyqtSignal()
    braggSearch = pyqtSignal(float)
    name = 'HitFindingView'

    def __init__(self, parent=None):
        super(HitFindingView, self).__init__(name=self.name)
        self.parent = parent
        self.ui = HitFinding_ui.Ui_Form()
        self.ui.setupUi(self)
        self.NPC_parameters  = {
                    'output_directory': self.getResultsPath,
                    # This num should be a general setting of the project
                    #'num': '1',
                    'output_formats': self.getOutFormats,
                    'data': self.getDataPath,
                    'filename_root': self.getFilenameRoot,
                    'file_extension': self.getFileExtension,
                    'cpus': self.getCpus,
                    'threshold': self.getThreshold,
                    'npixels': self.getNPixels,
                    'mask': self.getMaskPath,
                    'dark': self.getDarkFile,
                    'background_subtraction': self.getBKG,
                    'bragg_search': self.getBraggSearch,
                    'bragg_threshold': self.getBraggThreshold,
                    'roi': self.getROI}

        icon = QIcon(pkg.resource_filename('NPC','gui/icons/folder.svg'))
        for button in [self.ui.DataPathBut, self.ui.ResPathBut, self.ui.MaskPathBut, self.ui.DarkPathBut, self.ui.DataPathBut_2]:
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(18, 18))
        icon = QIcon(pkg.resource_filename('NPC','gui/icons/Delete.png'))
        for button in [self.ui.MaskDelBut, self.ui.DarkDelBut]:
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(17, 17))

        self.ui.DataPathBut.clicked.connect(lambda: self.setPath(self.ui.DataPath))
        self.ui.ResPathBut.clicked.connect(lambda: self.setPath(self.ui.ResultsPath))
        self.ui.findBraggBut.clicked.connect(self.findBraggs)

    def findBraggs(self):
        """ Find Position of Bragg peaks in the img
        and display it on screen  Should use the Braggs module"""
        try:
            threshold = float(self.ui.BraggThreshold.text())
            self.braggSearch.emit(threshold)
            return
        except ValueError:
                print("Bad input - Please check the value of Bragg Threshold parameter -")
                # self.ui.Log.appendPlainText("Bad input - Please check the value of Bragg Threshold parameter -")
                return

    def getDataPath(self):
        txt = str(self.ui.DataPath.text())
        if txt:
            return txt
        else:
            return None

    def getResultsPath(self):
        txt = str(self.ui.ResultsPath.text())
        if txt:
            return txt
        else:
            return None

    def getDarkFile(self):
        txt = str(self.ui.DarkPath.text())
        if txt:
            return txt
        else:
            return 'none'

    def getMaskPath(self):
        txt = str(self.ui.MaskPath.text())
        if txt:
            return txt
        else:
            return 'none'

    def getBKG(self):
        return str(self.ui.BKG_SUB.currentText())

    def getCpus(self):
        try:
            return int(self.ui.cpus.text())
        except ValueError:
            print('Integer expected for the number of cpus... Try Again.')
            return None

    def getFilenameRoot(self):
        return str(self.ui.RootSSX.text())

    def getFileExtension(self):
        return str(self.ui.FileExtensionSSX.text())

    def getOutFormats(self):
        s = ''
        if self.ui.hdf5out.isChecked():
            s += 'hdf5 '
        if self.ui.cctbxout.isChecked():
            s += 'pickles '
        if self.ui.cbfout.isChecked():
            s += 'cbf '
        return s

    def setPath(self, var):
        d = QFileDialog.getExistingDirectory(
            self,
            "Open a folder",
            self.parent.cwd,
            QFileDialog.ShowDirsOnly)
        var.setText(d)
        self.parent.cwd = d

        if var == self.ui.ResultsPath:
            self.setTable.emit()

    def getThreshold(self):
        try:
            return float(self.ui.Threshold.text())
        except ValueError:
            print('Integer expected for threshold value... Try Again.')
            return None

    def getNPixels(self):
        try:
            return float(self.ui.Npixels.text())
        except ValueError:
            print('Integer expected for the number of pixels above threshold... Try Again.')
            return None

    def getBraggSearch(self):
        s = str(self.ui.FindBragg.currentText())
        return s.strip().lower() == 'true'

    def getBraggThreshold(self):
        try:
            return int(self.ui.BraggThreshold.text())
        except ValueError:
            print('Integer expected for the bragg threshold... Try Again.')
            return None


    def getROI(self):
        if self.ui.checkBox.isChecked():
            try:
                x1 = int(self.ui.ROI_X1.text())
                x2 = int(self.ui.ROI_X2.text())
                y1 = int(self.ui.ROI_Y1.text())
                y2 = int(self.ui.ROI_Y2.text())
                s = '%4i %4i %4i %4i' % (y1, x1, y2, x2)

                return s
            except ValueError:
                print('Integer expected to define the region of interest... Try Again.')

                return 'None'
        else:
            return 'None'

    def getAllParameters(self):
        params = {}
        for key, value in self.NPC_parameters.items():
            print(key, value())
            params[key] = value()
        return params

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionHit_Finding')
            self.Pos = self.pos()
        else:
            self.close()


class HitLive(NPGWidget):

    sigUpdateROI = pyqtSignal(tuple)
    name = 'HitLiveView'

    def __init__(self, parent, resultReceiver, controlSender):
        super(HitLive, self).__init__(name=self.name)
        self.resultReceiver = resultReceiver
        self.controlSender = controlSender
        self.ui = LiveHF.Ui_HitFinding()
        self.ui.setupUi(self)
        self.parent = parent
        self.show()
        self.raise_()

        self.HiteRateItem= pg.PlotDataItem()
        self.ui.HitRateView.addItem(self.HiteRateItem)
        self.ui.HitRateView.enableAutoRange('xy', True)
        self.ui.ncpus.setDisabled(True)

        self.n_tmpFrames = 0
        self.n_tmpHits = 0
        self.total = 0
        self.totalHits = 0
        self.counter = 0

        self.shape = self.parent.XPView.detector.shape
        # Hit rate will be averaged over smoothingPeriod
        # As the plot is refreshed every second, this correspond to a minute of processing
        self.smoothingPeriod= 120
        self.nProcessed = np.zeros((self.smoothingPeriod,))
        self.nHits = np.zeros((self.smoothingPeriod,))

        self.zmqTimer = QtCore.QTimer()
        self.plotTimer = QtCore.QTimer()


        self.total = 0
        self.hitdata = np.zeros(100)
        self.percent = 0
        self.hr_data = np.zeros(100)

        # This is in the Qwidget HitWin
        QtCore.QObject.connect(self.ui.clearHitRate, QtCore.SIGNAL("clicked()"), self.clearHitRate)
        QtCore.QObject.connect(self.zmqTimer, QtCore.SIGNAL("timeout()"), self.receiveFromWorkers)
        QtCore.QObject.connect(self.plotTimer, QtCore.SIGNAL("timeout()"), self.plot)

        self.ui.thresh.editingFinished.connect(self.setThreshold)
        self.ui.UpdateROI.clicked.connect(self.resetROI)
        self.ui.npix.editingFinished.connect(self.setNPixels)
        self.ui.ROIX1.editingFinished.connect(self.getROI)
        self.ui.ROIX2.editingFinished.connect(self.getROI)
        self.ui.ROIY1.editingFinished.connect(self.getROI)
        self.ui.ROIY2.editingFinished.connect(self.getROI)
        #self.ui.FastScan.toggled.connect(self.OnFastScanToggled)
        #self.ui.ShootNTrap.toggled.connect(self.OnShootNTrapToggled)
        #self.ui.NShots.editingFinished.connect(self.setNShots)

        self.zmqTimer.start(250)
        self.plotTimer.start(1000)


    def clearHitRate(self):
        self.hr_data = np.zeros(100)
        #self.processed_img.fill(0)
        #self.hits.fill(0)
        self.HiteRateItem.setData([0])
        self.count_temp = 0

    def OnFastScanToggled(self):
        self.controlSender.send_json({"RADDAM" : False})
        #self.ui.NShots.setDisabled(True)

    def OnShootNTrapToggled(self):
        try:
            NShots = int(self.ui.NShots.text())
            self.controlSender.send_json({"RADDAM": True, "NShots": NShots})
        except ValueError:
            print("Please use an integer for this parameter...")

    def setNShots(self):
        try:
            NShots = int(self.ui.NShots.text())
            self.controlSender.send_json({"NShots": NShots})
        except ValueError:
            print("Please use an integer for this parameter...")

    def setThreshold(self):
        try:
            thresh = int(self.ui.thresh.text())
            self.controlSender.send_json({"threshold" : thresh})
            #Log("HitFinding Threshold value changed to %i"%self.HFParams.threshold.value)
        except ValueError:
            print("Please use an integer for this parameter...")

            #Log("Threshold value should be an integer")
            #self.ui.thresh.setText(str(self.HFParams.threshold.value))

    def setNPixels(self):
        try:
            npixels = int(self.ui.npix.text())
            self.controlSender.send_json({"npixels" : npixels})
            #Log("HitFinding Npixels value changed to %i\n"%self.HFParams.npixels.value)

        except ValueError:
            #Log("Npixels value should be an integer")
            #self.HitWin.uiHit.npix.setText(str(self.HFParams.npixels.value))
            pass

    def setROI(self, roi):
        x1, y1, x2, y2 = roi
        print(x1,y1,x2,y2)
        x1 = int(max(0, x1))
        y1 = int(max(0, y1))
        x2 = int(min(self.shape[1], x2))
        y2 = int(min(self.shape[0], y2))
        self.ui.ROIX1.setText(str(x1))
        self.ui.ROIX2.setText(str(x2))
        self.ui.ROIY1.setText(str(y1))
        self.ui.ROIY2.setText(str(y2))
        print(self.shape)
        self.controlSender.send_json({'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2})

    def setLabel(self):
        if "Hide" in str(self.ui.ShowROI.text()):
            self.ui.ShowROI.setText("Show ROI")
        else:
            self.ui.ShowROI.setText("Hide ROI")

    def getROI(self):
        #roi = getattr(self.ui, obj)
        try:
            x1 = int(self.ui.ROIX1.text())
            if x1 < 0:
                x1 = 0
                self.ui.ROIX1.setText(str(x1))

            y1 = int(self.ui.ROIY1.text())
            if y1 < 0:
                y1 = 0
                self.ui.ROIY1.setText(str(y1))

            x2 = int(self.ui.ROIX2.text())
            if x2 < x1:
                x2 = x1 + 1
                self.ui.ROIX2.setText(str(x2))
            if x2 > self.shape[1]:
                x2 = self.shape[1]
                self.ui.ROIX2.setText(str(x2))

            y2 = int(self.ui.ROIY2.text())
            if y2 < y1:
                y2 = y1 + 1
                self.ui.ROIY2.setText(str(y2))
            if y2 > self.shape[0]:
                y2 = self.shape[0]
                self.ui.ROIY2.setText(str(y2))


            self.controlSender.send_json({'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2})
            self.sigUpdateROI.emit((x1, y1, x2, y2))

        except ValueError:
            self.ui.HitLog.appendPlainText("Roi values should be integers")

    def resetROI(self):
        x1 = 0
        y1 = 0
        x2 = self.shape[1]
        y2 = self.shape[0]
        self.ui.ROIX1.setText(str(x1))
        self.ui.ROIX2.setText(str(x2))
        self.ui.ROIY1.setText(str(y1))
        self.ui.ROIY2.setText(str(y2))
        self.controlSender.send_json({'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2})
        self.sigUpdateROI.emit((x1, y1, x2, y2))

    def sendResetMP(self):
        self.controlSender.send_json({"resetMP":"resetMP"})

    def receiveFromWorkers(self):
        while True:
            try:
                result_message = self.resultReceiver.recv_json(flags=zmq.NOBLOCK)
                self.n_tmpFrames += result_message['processed']
                self.n_tmpHits += result_message['hits']

            except:
                break

    def plot(self):
        if self.n_tmpFrames > 0:
            self.nProcessed[ self.counter % self.smoothingPeriod] = self.n_tmpFrames
            self.total += self.n_tmpFrames
            self.n_tmpFrames = 0
            self.nHits[self.counter % self.smoothingPeriod] = self.n_tmpHits
            self.totalHits += self.n_tmpHits
            self.n_tmpHits = 0

            self.percent = (float(self.nHits.sum()) / self.nProcessed.sum() * 100.)
            if self.counter < 100:
                self.hr_data[self.counter] = self.percent
                self.HiteRateItem.setData(self.hr_data[0:self.counter+1])
                self.ui.HitRateView.setLabel('bottom',' Time (s)  //  Hit Rate %3.1f%%'%self.percent)
            else:
                self.hr_data[:-1] = self.hr_data[1:]
                self.hr_data[-1] = self.percent
                self.HiteRateItem.setData(self.hr_data)
                self.HiteRateItem.setPos(self.counter,0)
                self.ui.HitRateView.setLabel('bottom',' Time (s)  //  Hit Rate %3.1f%%'%self.percent)
            self.ui.HitLog.appendPlainText(Log("Processing @ %5i fps - %8i images processed - %8i hits" % (self.nProcessed[ self.counter % self.smoothingPeriod], self.total, self.totalHits)))
            self.counter += 1

    def closeEvent(self, evt):
        if evt.spontaneous():
            self.hide()
            self.visible = False
            self.hideMe.emit('actionHit_Viewer')
            self.Pos = self.pos()
        else:
            self.close()
