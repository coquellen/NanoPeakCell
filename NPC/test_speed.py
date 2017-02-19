from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.widgets.RemoteGraphicsView
import numpy as np

app = pg.mkQApp()

view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
pg.setConfigOptions(antialias=True)  ## this will be expensive for the local plot
view.pg.setConfigOptions(antialias=True)  ## prettier plots at no cost to the main process!
view.setWindowTitle('pyqtgraph example: RemoteSpeedTest')

label = QtGui.QLabel()
rcheck = QtGui.QCheckBox('plot remote')
rcheck.setChecked(True)
lcheck = QtGui.QCheckBox('plot local')
lplt = pg.PlotWidget()
layout = pg.LayoutWidget()
layout.addWidget(rcheck)
layout.addWidget(lcheck)
layout.addWidget(label)
layout.addWidget(view, row=1, col=0, colspan=3)
layout.addWidget(lplt, row=2, col=0, colspan=3)
layout.resize(800, 800)
layout.show()

## Create a PlotItem in the remote process that will be displayed locally
rplt = view.pg.PlotItem()
rplt._setProxyOptions(deferGetattr=True)  ## speeds up access to rplt.plot
view.setCentralItem(rplt)

lastUpdate = pg.ptime.time()
avgFps = 0.0


def update():
    global check, label, plt, lastUpdate, avgFps, rpltfunc
    data = np.random.normal(size=(10000, 50)).sum(axis=1)
    data += 5 * np.sin(np.linspace(0, 10, data.shape[0]))

    if rcheck.isChecked():
        rplt.plot(data, clear=True, _callSync='off')  ## We do not expect a return value.
        ## By turning off callSync, we tell
        ## the proxy that it does not need to
        ## wait for a reply from the remote
        ## process.
    if lcheck.isChecked():
        lplt.plot(data, clear=True)

    now = pg.ptime.time()
    fps = 1.0 / (now - lastUpdate)
    lastUpdate = now
    avgFps = avgFps * 0.8 + fps * 0.2
    label.setText("Generating %0.2f fps" % avgFps)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(0)

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()