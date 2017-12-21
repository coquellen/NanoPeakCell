from __future__ import print_function
import multiprocessing
import fabio
import h5py
from .utils import Log
import time
import numpy as np
import os
from .Braggs import find_peaks
from .NPC_CBF import write as write_CBF
from mpi.NPC_routines import InitDetector, ROI

# Carefull 3.5
try:
    import Queue
except ImportError:
    import queue as Queue
import cPickle
from PyQt4 import QtCore



def dpack(active_areas=None,
          address=None,
          beam_center_x=None,
          beam_center_y=None,
          ccd_image_saturation=None,
          data=None,
          distance=None,
          pixel_size=None,
          saturated_value=None,
          timestamp=None,
          wavelength=None,
          xtal_target=None,
          min_trusted_value=None):

    """ XXX Check completeness.  Should fill in sensible defaults."""

    # Must have data.
    if data is None:
        return None

    # Create a time stamp of the current time if none was supplied.
    if timestamp is None:
        timestamp = None

    # For unknown historical reasons, the dictionary must contain both
    # CCD_IMAGE_SATURATION and SATURATED_VALUE items.
    # if ccd_image_saturation is None:
    #    if saturated_value is None:
    #        ccd_image_saturation = cspad_saturated_value
    #    else:
    #        ccd_image_saturation = saturated_value
    # if saturated_value is None:
    #    saturated_value = ccd_image_saturation

    # Use a minimum value if provided for the pixel range
    if min_trusted_value is None:
        # min_trusted_value = cspad_min_trusted_value
        min_trusted_value = None

    # By default, the beam center is the center of the image.  The slow
    # (vertical) and fast (horizontal) axes correspond to x and y,
    # respectively.
    if beam_center_x is None:
        beam_center_x = pixel_size * data.focus()[1] / 2
    if beam_center_y is None:
        beam_center_y = pixel_size * data.focus()[0] / 2

    # By default, the entire detector image is an active area.  There is
    # no sensible default for distance nor wavelength.  XXX But setting
    # wavelength to zero may be disastrous?
    if active_areas is None:
        # XXX Verify order with non-square detector
        active_areas = flex.int((0, 0, data.focus()[0], data.focus()[1]))
    if distance is None:
        distance = 0
    if wavelength is None:
        wavelength = 0

    # The size must match the image dimensions.  The length along the
    # slow (vertical) axis is SIZE1, the length along the fast
    # (horizontal) axis is SIZE2.
    return {'ACTIVE_AREAS': active_areas,
            'BEAM_CENTER_X': beam_center_x,
            'BEAM_CENTER_Y': beam_center_y,
            'CCD_IMAGE_SATURATION': ccd_image_saturation,
            'DATA': data,
            'DETECTOR_ADDRESS': address,
            'DISTANCE': distance,
            'PIXEL_SIZE': pixel_size,
            'SATURATED_VALUE': saturated_value,
            'MIN_TRUSTED_VALUE': min_trusted_value,
            'SIZE1': data.focus()[0],
            'SIZE2': data.focus()[1],
            'TIMESTAMP': timestamp,
            'SEQUENCE_NUMBER': 0,  # XXX Deprecated
            'WAVELENGTH': wavelength,
            'xtal_target': xtal_target}

### Python3 ?
try:
    #from libtbx import easy_pickle
    #from scitbx.array_family import flex
    cctbx = True
except SyntaxError:
    cctbx = False

class Signals(QtCore.QObject):
    HitSignal = QtCore.pyqtSignal(np.ndarray)
    Stop = QtCore.pyqtSignal(bool)
    Job = QtCore.pyqtSignal(list)

class HitManager(object):

    def __init__(self, queue):
        self.queue = queue
        self.counter = 0
        self.Nhit = 0
        self.N = 0
        self.fnsHit = ''
        self.fnsRej = ''
        self.group = None
        self.data = []

    def add(self, hit, chunk, fns, group=None):
        self.Nhit += hit
        self.N += chunk
        self.group = group
        self.counter += 1

        if hit == 1:
            self.fnsHit += fns+'\n'
        else: self.fnsRej += fns+'\n'

        if self.counter % 10 ==0:
            self.send()


    def send(self):
        self.queue.put((self.Nhit, self.N, self.fnsHit, self.fnsRej, self.group))
        self.counter = 0
        self.Nhit = 0
        self.N = 0
        self.fnsHit = ''
        self.group = None


class MProcess(multiprocessing.Process):

    def __init__(self, task_queue, result_queue, options, ai, detector, name):
        multiprocessing.Process.__init__(self)
        self.name = name
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.options = options
        self.detector = detector
        self.AzimuthalIntegrator = ai
        self.count = 0
        self.Nhits = 0
        self.NFramesPerH5 = 100
        self.h5out = None
        self.dset = None
        self.manager = HitManager(self.result_queue)
        self.exit = multiprocessing.Event()

        self.saveFormat = {'cbf': ['CBF', 'cbf', self.saveCbf],
                           'hdf5': ['HDF5', 'h5', self.saveH5],
                           'pickles': ['PICKLES', 'pickle', self.savePickle]}

        #Defining ROI
        # This should be done in an object
        # See in mpi NPC_Routines
        self.roi = ROI(self.options, self.detector.shape)


        #All this should be done in a
        if self.options['background_subtraction'].lower() != 'none':
            self.type = np.float32
            self.SubtractBkg = True
        else:
            self.type = np.int32
            self.SubtractBkg = False

        self.mask = self.getMask()
        self.dark = self.getCorrection(self.options['dark'])

        self.data = np.zeros((self.roi.xmax-self.roi.xmin, self.roi.ymax-self.roi.ymin))

        if self.options['dark'].lower() == 'none':
                self.correctData = self.NoCorrect
                self.SubtractDark = True
        else:
                self.correctData = self.CorrectDark
                self.SubtractDark = False

    def getMask(self):
        m = self.getCorrection(self.options['mask'])
        if m is None:
            return self.detector.mask.astype(np.int32)
        else:
            return m.astype(np.int32)

    def getCorrection(self, options):
        if options.lower() == 'none':
          return None
        else:
          return self.open(options)
    
    def NoCorrect(self, data, dark, mask):
        return data

    def CorrectDark(self, data, dark, roi):
        xmin, xmax, ymin, ymax = roi
        return data.astype(np.int32) - dark[xmin:xmax,ymin:ymax]
    
    def open(self,fn):
        if fn.endswith('.h5'):
            h5 = h5py.File(fn)
            return h5['data'][:].astype(np.int32)
        elif fn.endswith('.pickle'):
            return None
        else:
            img = fabio.open(fn)
            return img.data[:]


    def run(self):
        while not self.exit.is_set() :
            try:
                    next_task = self.task_queue.get()
                    if next_task is None:
                        #self.exitProperly()
                        break
                    else:
                        self.task_queue.task_done()
                        self.isHit(next_task)

            except KeyboardInterrupt:
                self.exitProperly()
                return
        self.exitProperly()
        return

    def shutDown(self):
        #print("Process %s received signal" % self.name)
        self.exit.set()

    def exitProperly(self):
        try:
            self.task_queue.task_done()
        except ValueError: pass
        self.manager.send()
        size = self.Nhits % self.NFramesPerH5
        shape = (size, self.detector.shape[0], self.detector.shape[1])

        if self.dset is not None:
            self.dset.resize(shape)
            if self.options["bragg_search"]:
                self.nPeaks.resize((size,))
                self.peakXPosRaw.resize((size, 2000))
                self.peakYPosRaw.resize((size, 2000))
                self.peakTotalIntensity.resize((size, 2000))
        if self.h5out is not None: self.h5out.close()
        print("Process %s exited Properly" % self.name)

    def isHit(self,filename):

        #
        try:
            self.img = fabio.open(filename)
        except AssertionError:
            time.sleep(1)
            self.img = fabio.open(filename)

        self.data = self.correctData(
                    self.img.data[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax].astype(np.int32),
                    self.dark,
                    self.roi)
        #

        # BKG Sub using mask
        # TODO: Include it in the correctData part
        # TODO: Use the new Correction class as in the MPI part
        if self.SubtractBkg:
            if self.data.shape == self.detector.shape:
                self.data = \
                    self.AzimuthalIntegrator.ai.separate(self.data.astype("float64"), npt_rad=1024, npt_azim=512,
                                                         unit="2th_deg",
                                                         percentile=50, mask=self.mask,
                                                         restore_mask=True)[0][:]

        # Masking Array
        masked = np.ma.array(self.data, mask=self.mask[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax])

        # Hit Finding
        hit = int( np.count_nonzero(masked.compressed() > self.options['threshold']) >= self.options['npixels'])

        #Could delay that
        self.manager.add(hit, 1, filename, None)

        if len(self.options['output_formats'].split()) > 0 and hit > 0:
            if self.roi.active:
                self.data = self.correctData(self.img.data,
                                             self.dark,
                                             (0, self.detector.shape[0], 0, self.detector.shape[1]))

            self.saveHit(filename)

    def setOutputRoot(self, fname):
        self.root, self.extension = os.path.splitext(os.path.basename(fname))

    def saveHit(self, fname):

        self.setOutputRoot(fname)

        #TODO : Bragg Search here - Save to txt file or H5


        for outputFormat in self.options['output_formats'].split():
            dirStr, extStr, func = self.saveFormat[outputFormat]
            OutputFileName = os.path.join(self.options['output_directory'],
                                          'NPC_run%s' % (self.options['num'].zfill(3)),
                                          dirStr,
                                          self.root)
                                          #"%s.%s" % (self.root, extStr))

            func(OutputFileName,extStr)

    def saveCbf(self, OutputFileName,extStr):
        fname = '%s_%s_%s.%s'%(OutputFileName,
                               str(self.count).zfill(6),
                               self.name,
                               extStr)
        write_CBF(fname,self.data.astype(np.int32))


    def savePickle(self, OutputFileName,extStr):
        #if cctbx:
            ovl = self.getOvl()
            pixels = flex.int(self.data.astype(np.int32))
            pixel_size = self.detector.pixel1
            data = dpack(data=pixels,
                         distance=self.options['distance'],
                         pixel_size=pixel_size,
                         wavelength=self.options['wavelength'],
                         beam_center_x=self.options['beam_y'] * pixel_size,
                         beam_center_y=self.options['beam_x'] * pixel_size,
                         ccd_image_saturation=ovl,
                         saturated_value=ovl)
            easy_pickle.dump('%s.%s'%(OutputFileName,extStr), data)


    def saveH5(self, OutputFileName,extStr):
        if self.Nhits % self.NFramesPerH5 == 0:
            if self.h5out is not None: self.h5out.close()
            OutputFileName = os.path.join(self.options['output_directory'],
                                          'NPC_run%s' % (self.options['num'].zfill(3)),
                                          'HDF5',
                                          "%s_%s_%i.h5" % (
                                          self.options['filename_root'], self.name,
                                          self.Nhits / self.NFramesPerH5))
            self.h5out = h5py.File(OutputFileName, 'w')
            self.dset = self.h5out.create_dataset("data",
                                                  (self.NFramesPerH5, self.detector.shape[0], self.detector.shape[1]),
                                                  compression="gzip", dtype=np.float32)
            if self.options['bragg_search']:
                self.nPeaks = self.h5out.create_dataset("nPeaks", (self.NFramesPerH5,), dtype=np.int32, chunks=(1,))
                self.peakTotalIntensity = self.h5out.create_dataset("peakTotalIntensity",
                                                                    (self.NFramesPerH5, 2000),
                                                                    maxshape=(self.NFramesPerH5, None))

                self.peakXPosRaw = self.h5out.create_dataset("peakXPosRaw",
                                                             (self.NFramesPerH5, 2000),
                                                             maxshape=(self.NFramesPerH5, None))

                self.peakYPosRaw = self.h5out.create_dataset("peakYPosRaw",
                                                             (self.NFramesPerH5, 2000),
                                                             maxshape=(self.NFramesPerH5, None))

        self.dset[self.Nhits % self.NFramesPerH5, ::] = self.data[:]

        if self.options['bragg_search']: #and np.count_nonzero(self.data > self.options['bragg_threshold']) < 10000:

            X, Y, I = find_peaks(self.data * -1 * (self.mask - 1), self.options['bragg_threshold'])

            # If more than 2000k bragg peaks - restrain to the first 2k
            dim2 = min(X.size,2000)
            idx = self.Nhits % self.NFramesPerH5
            self.nPeaks[idx] = dim2
            self.peakXPosRaw[idx, 0:dim2] = X[0:dim2].reshape(1, dim2)
            self.peakYPosRaw[idx, 0:dim2] = Y[0:dim2].reshape(1, dim2)
            self.peakTotalIntensity[idx, 0:dim2] = I[0,0:dim2]

        self.Nhits += 1

    def getOvl(self):
        if 'pilatus' in self.detector.name.lower(): ovl = 1048500
        elif 'eiger' in self.detector.name.lower(): ovl = self.ovl
        else: ovl = None
        return ovl


class MProcessEiger(MProcess):
    def __init__(self, task_queue, result_queue, options, AzimuthalIntegrator, detector, name):
        MProcess.__init__(self,  task_queue, result_queue, options, AzimuthalIntegrator, detector, name)
        self.h5 = None
        self.h5_filename = None
        self.NFramesPerH5 = 100
        self.h5out = None
        self.dset = None
        self.data = np.zeros((self.roi.xmax - self.roi.xmin, self.roi.ymax - self.roi.ymin), dtype=self.type)
        self.count = 0
        self.manager = HitManager(self.result_queue)


    def isHit(self,task):

        #The task should be a dict, then no need to worry about number of elements in it
        self.h5in, self.group, self.ovl, self.type, N = task
        self.h5 = h5py.File(self.h5in,'r')

        if type(N) is int:
            iterable = range(0,N)
        else:
            iterable = N

        for i in iterable:
          if not self.exit.is_set():
            #Dark Correction
            if self.options['background_subtraction'].lower() != 'none':
                # if self.data.shape == self.detector.shape:
                
                self.data = \
                    self.AzimuthalIntegrator.ai.separate(\
                        self.correctData(self.h5[self.group][i,::].astype(np.int32),
                                         self.dark,
                                         self.options['ROI_tuple']),
                        npt_rad=1024, npt_azim=512,
                        unit="2th_deg",
                        percentile=50,
                        mask=self.mask,
                        restore_mask=True)[0][self.roi.xmin:self.roi.xmax,self.roi.ymin:self.roi.ymax]

            else:

                self.data = self.correctData(self.h5[self.group][i,self.roi.xmin:self.roi.xmax,self.roi.ymin:self.roi.ymax].astype(np.int32),
                                         self.dark,
                                         self.options['ROI_tuple'])
            


            masked = np.ma.array(self.data,
                                 mask=self.mask[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax])


            #Hit Finding
            hit = int( np.count_nonzero(masked.compressed() > self.options['threshold']) >= self.options['npixels'])
            self.manager.add(hit,1,'%s //%i' % (self.h5in,i), self.group)


            if len(self.options['output_formats'].split()) > 0 and hit > 0:
                if self.roi.active:
                    self.data = self.correctData(self.h5[self.group][i,::],
                                                 self.dark,
                                                 (0,self.detector.shape[0],0,self.detector.shape[1]))

                self.saveHit(self.h5in,i)

                self.count += 1
        self.h5.close()
        return

    def saveHit(self, fname, idx):

        self.setOutputRoot(fname)

        #TODO : Bragg Search here - Save to txt file or H5


        for outputFormat in self.options['output_formats'].split():
            dirStr, extStr, func = self.saveFormat[outputFormat]
            OutputFileName = os.path.join(self.options['output_directory'],
                                          'NPC_run%s' % (self.options['num'].zfill(3)),
                                          dirStr,
                                          '%s_%s'%(self.root, str(idx).zfill(4)))
                                          #"%s.%s" % (self.root, extStr))

            func(OutputFileName,extStr)

    def saveCbf(self, OutputFileName,extStr):
        fname = '%s.%s'%(OutputFileName,
                               extStr)
        write_CBF(fname,self.data.astype(np.int32))


    def savePickle(self, OutputFileName,extStr):
        #if cctbx:
            ovl = self.getOvl()
            pixels = flex.int(self.data.astype(np.int32))
            pixel_size = self.detector.pixel1
            data = dpack(data=pixels,
                         distance=self.options['distance'],
                         pixel_size=pixel_size,
                         wavelength=self.options['wavelength'],
                         beam_center_x=self.options['beam_y'] * pixel_size,
                         beam_center_y=self.options['beam_x'] * pixel_size,
                         ccd_image_saturation=ovl,
                         saturated_value=ovl)

            cPickle.dump(data, open('%s.%s'%(OutputFileName,extStr), "wb"), cPickle.HIGHEST_PROTOCOL)
            #easy_pickle.dump('%s.%s'%(OutputFileName,extStr), data)


    def saveH5(self, OutputFileName,extStr):
        if self.Nhits % self.NFramesPerH5 == 0:
            if self.h5out is not None: self.h5out.close()
            OutputFileName = os.path.join(self.options['output_directory'],
                                          'NPC_run%s' % (self.options['num'].zfill(3)),
                                          'HDF5',
                                          "%s_%s_%i.h5" % (
                                          self.options['filename_root'], self.name,
                                          self.Nhits / self.NFramesPerH5))
            self.h5out = h5py.File(OutputFileName, 'w')
            self.dset = self.h5out.create_dataset("data",
                                                  (self.NFramesPerH5, self.detector.shape[0], self.detector.shape[1]),
                                                  compression="gzip", dtype=np.float32)
            if self.options['bragg_search']:
                self.nPeaks = self.h5out.create_dataset("nPeaks", (self.NFramesPerH5,), dtype=np.int32, chunks=(1,))
                self.peakTotalIntensity = self.h5out.create_dataset("peakTotalIntensity",
                                                                    (self.NFramesPerH5, 2000),
                                                                    maxshape=(self.NFramesPerH5, None))

                self.peakXPosRaw = self.h5out.create_dataset("peakXPosRaw",
                                                             (self.NFramesPerH5, 2000),
                                                             maxshape=(self.NFramesPerH5, None))

                self.peakYPosRaw = self.h5out.create_dataset("peakYPosRaw",
                                                             (self.NFramesPerH5, 2000),
                                                             maxshape=(self.NFramesPerH5, None))

        self.dset[self.Nhits % self.NFramesPerH5, ::] = self.data[:]

        if self.options['bragg_search']: #and np.count_nonzero(self.data > self.options['bragg_threshold']) < 10000:

            X, Y, I = find_peaks(self.data * -1 * (self.mask - 1), self.options['bragg_threshold'])

            # If more than 2000k bragg peaks - restrain to the first 2k
            dim2 = min(X.size,2000)
            idx = self.Nhits % self.NFramesPerH5
            self.nPeaks[idx] = dim2
            self.peakXPosRaw[idx, 0:dim2] = X[0:dim2].reshape(1, dim2)
            self.peakYPosRaw[idx, 0:dim2] = Y[0:dim2].reshape(1, dim2)
            self.peakTotalIntensity[idx, 0:dim2] = I[0,0:dim2]

        self.Nhits += 1



    def exitProperly(self):

        try:
            self.task_queue.task_done()
        except ValueError:
            pass

        # For Eiger purpose
        if self.h5 is not None:
            try:
                self.h5.close()
            except ValueError:
                pass

        size = self.Nhits % self.NFramesPerH5
        shape = (size, self.detector.shape[0], self.detector.shape[1])

        if self.dset is not None:
            self.dset.resize(shape)
            if self.options["bragg_search"]:
                self.nPeaks.resize((size,))
                self.peakXPosRaw.resize((size, 2000))
                self.peakYPosRaw.resize((size, 2000))
                self.peakTotalIntensity.resize((size, 2000))
        if self.h5out is not None: self.h5out.close()
        print("Process %s exited Properly" % self.name)
