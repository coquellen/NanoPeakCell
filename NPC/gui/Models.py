import fabio
import h5py
try:
    import cPickle
except:
    import _pickle as cPickle
import os
try:
    from PyQt5.QtCore import pyqtSignal, QObject
except:
    from PyQt4.QtCore import  pyqtSignal, QObject

import numpy as np
from NPC.gui.geom import Geom, parse_geom_file_quadrants
import NPC.gui.peakfind as pf



def visitor_func(h5):
    for key in h5.keys():
        node = h5[key]
        if isinstance(node, h5py.Dataset):
            if len(node.shape) == 2 and node.size > 512 * 512:
                t = (1, node.shape[0], node.shape[1])
                return node.name, t


            if len(node.shape) == 3 and node.shape[1] * node.shape[2] > 512 * 512:
                return node.name, node.shape


        else:
            visitor_func(node)

def load_pickle(file_name, faster_but_using_more_memory=True):
  """
  Wraps cPickle.load.

  Parameters
  ----------
  file_name : str
  faster_but_using_more_memory : bool, optional
      Optionally read the entirety of a file into memory before converting it
      into a python object.

  Returns
  -------
  object
  """
  if (faster_but_using_more_memory):
    return cPickle.loads(open(file_name, "rb").read())
  return cPickle.load(open(file_name, "rb"))


class CrystFelStream(QObject):

    def __init__(self):
        pass


class OpenImage(object):
    def __init__(self):
        self.h5 = None
        self.h5Filename = None

    def openFrame(self, args):
        try:
            fn, path, index = args[0]
        except ValueError:
            fn, path, index = args
        ext = os.path.splitext(fn)[1]
        if 'pickle' in ext:
            return self.openPickle(fn)
        elif 'h5' in ext:
            return self.openH5(fn, path, index)
        else:
            return self.openImg(fn)

    def openH5(self, fn, path='/data', index=None):
        if fn != self.h5Filename:
            self.h5Filename = fn
            if self.h5 is not None: self.h5.close()
            self.h5 = h5py.File(fn)
        if index is None:
            if len(self.h5[path].shape) == 3:
                #print("Called")
                #print(self.h5[path][0,::].astype(np.int32))
                return self.h5[path][0,::].astype(np.int32), None
            else:
                return self.h5[path][:].astype(np.int32), None
        else:
            return self.h5[path][index, ::].astype(np.int32), None

    def openImg(self, fn):
        img = fabio.open(fn)
        self.header = img.header

        return img.data, dict(img.header)

    def openPickle(self, fn):
        img = load_pickle(self.fn)
        # This code snippet helps to remove the border of each tile of the CSPAD (lots of overload)
        #
        # data = img['DATA'].as_numpy_array()
        # mask = np.where(data > 0, 0, 1)
        # s = ndimage.generate_binary_structure(2, 1)
        # self.dset = data*np.logical_not(ndimage.binary_dilation(mask, structure =s ))
        return img['DATA'].as_numpy_array(), None

    def shutDown(self):
        if self.h5 is not None:
            self.h5.close()
            self.h5Filename = None
            self.h5 = None


class NPGData(QObject):

    updateImageView = pyqtSignal(np.ndarray)
    updateXParams = pyqtSignal(dict)
    updateStream = pyqtSignal(tuple)
    #dataReceived = pyqtSignal(tuple)
    binning = 2

    def __init__(self):
        super(NPGData, self).__init__()
        self.header = None
        self.data = None
        self.loadedDark = None
        self.dark = None
        self.loadedMask = False
        self.mask = None
        self.loadedGeom = False
        self.geom = Geom()
        self.IO = OpenImage()
        self.MaxOverThreshold = 10000
        self.loadedstream = False
        #self.socketTimer = QTimer()
        #self.socketTimer.timeout.connect(self.receiveMSG)

    def updateData(self, *args):
        #data  = self.IO.openFrame(args)
        self.data, self.header = self.IO.openFrame(args)
        self.applyCorrection()
        self.updateImageView.emit(self.data)
        if self.header is not None:
            self.updateXParams.emit(self.header)
        if self.loadedstream:
            self.updateStream.emit(args)

    def updateMask(self, fn):
        ext = os.path.splitext(str(fn))[1]
        path = None
        if 'h5' in ext:
            with h5py.File(fn, 'r') as h5:
                path, shape = visitor_func(h5)
        self.mask = -1 * (self.IO.openFrame((fn, path, None)) - 1)
        self.loadedMask = True
        if self.data is not None:
            self.applyCorrection()
            self.updateImageView.emit(self.data)

    def updateStreamGeom(self, fn):
        self.updateGeom(str(fn), openfn=False)
        #if len(self.geom[0]) > 1: self.DetTransfo = getGeomTransformations(self.geom[0])

        #self.panels = self.geom[0].keys()
        #params = self.geom[0][self.geom[0].keys()[0]]
        #self.ss = int(params[1]) - int(params[0]) + 1
        #self.fs = int(params[3]) - int(params[2]) + 1
        #print("Geom updated")

    def updateGeom(self, fn, openfn=True):
        #self.geom = parse_geom_file(fn, openfn=openfn)
        self.geom.load(fn, openfn)
        self.loadedGeom = True
        if self.data is not None:
            self.applyCorrection()
            self.updateImageView.emit(self.data)

    def updateGeomQuad(self, fn, openfn=True):
        geom, shape, self.quad = parse_geom_file_quadrants(fn, openfn=openfn)
        self.geom = geom, shape
        self.loadedGeom = True
        if self.data is not None:
            self.applyCorrection()
            self.updateImageView.emit(self.data)



    def applyCorrection(self):
        if self.loadedMask:
            if self.data.shape == self.mask.shape:
                self.data *= self.mask.astype(self.data.dtype)
                #print("Mask Correction Applied")
            else:
                print("Mask Correction NOT Applied: Mask dimensions not appropriate")

        if self.loadedDark:
            print("Dark Correction Applied")
            self.data -= self.dark

        if self.loadedGeom:
            if self.data.shape == self.geom.size:
                print("Geometry transformation applied")
                self.data = self.geom.reconstruct(self.data)
            else:
                print("Geometry transformation NOT Applied: Geometry dimensiosn not appropriate")

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

        #shapeOut = (shapeIn[0] // self.binning, shapeIn[1] / self.binning)
        temp = data[0:dim1Out * self.binning, 0:dim2Out * self.binning].astype("float32")
        temp.shape = (dim1Out, self.binning, dim2Out, self.binning)
        return temp.max(axis=3).max(axis=1).astype(data.dtype)
        #return out.astype(data.dtype)

    def findBragg(self, threshold):
        if self.data is not None:
            #data = self.data.astype(np.int32)
            N = np.count_nonzero(self.data > threshold)
            if N > self.MaxOverThreshold:
                #self.ui.Log.appendPlainText(
                print("Bragg search aborted... A threshold value of %i does not seem appropriate for this pattern." % threshold)
                #if self.filename_cache != self.imgfact.filename:
                self.max_t = np.sort(self.data, axis=None)[-1000]
                #self.filename_cache = self.imgfact.filename
                #self.ui.Log.appendPlainText(
                print("Bragg search will be allowed for threshold values equal to or above %i for this pattern." % self.max_t)
                return None
            self.peaks = pf.local_maxima(self.data.astype(np.int32), 3, 3, threshold)
            num_braggs = len(self.peaks)

            #if num_braggs > self.MaxBraggs:
            #    self.ui.Log.appendPlainText(
            #        "Too many Bragg peaks have been found to be displayed (%i). Please consider adjusting your threshold.\n" % len(
            #            self.peaks))
            #else:
            #self.ui.Log.appendPlainText(
            print("Found %4i Bragg peaks  (threshold of %i)" % (
                    num_braggs, threshold))

            return self.peaks
            #self.display_peaks(self.peaks)
            #self.ShowBraggs = True
            #self.ui.actionShow_Bragg_Peaks.setText("Hide Bragg Peaks")

                #def startZMQPull(self, host, port):
    #    if host == 'localhost': host = '127.0.0.1'
    #    self.ZMQPull = ZMQPull(host = host, port=port, opts=[zmq.CONFLATE], flags=zmq.NOBLOCK)
    #    self.socketTimer.start(500)

    #def receiveMSG(self):
    #    try:
    #        data = self.ZMQPull.receive()
    #        fn = str(data['fn'].strip())
    #        path = str(data['path'])
    #        index = int(data['index'])
    #        self.updateData(fn, path, int(index))
    #        return
    #    except zmq.error.Again:
    #        return





