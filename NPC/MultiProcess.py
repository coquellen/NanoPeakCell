from __future__ import print_function
import multiprocessing
import fabio
import h5py
from .utils import Log, get_filenames
import time
import numpy as np
import os
from .Braggs import find_peaks
from NPC_CBF import write as write_CBF

# Carefull 3.5
try:
    import Queue
except ImportError:
    import queue as Queue
import sys
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
    from libtbx import easy_pickle
    from scitbx.array_family import flex
    cctbx = True
except ImportError or SyntaxError:
    cctbx = False

class Signals(QtCore.QObject):
    HitSignal = QtCore.pyqtSignal(np.ndarray)
    Stop = QtCore.pyqtSignal(bool)
    Job = QtCore.pyqtSignal(list)


# Not used anymore
class DisplayResults(multiprocessing.Process):

    def __init__(self, nqueue, results_queue,options, log):
        multiprocessing.Process.__init__(self)
        self.t1 = time.time()
        self.hit = 0
        self.out = 0
        self.total = 0
        self.log = log
        self.print_function = print
        self.signals = Signals()
        self.Nqueue = nqueue
        self.results = results_queue
        self.options = options

    def run(self):
        if self.options["live"]:
            try:
                while True:
                    self.displayStats()

            except KeyboardInterrupt:
                print("\n\nCtrl-c received! --- Aborting and trying not to compromising results...")

        else:
            while self.out != self.total or self.out == 0:
                try:
                    self.displayStats()
                except KeyboardInterrupt:
                    print("\n\nCtrl-c received --- Aborting and trying not to compromising results...")
                    break

            self.displayFinalStats()

    def displayStats(self):

            while True or self.out != self.total:
                try:
                    self.total = self.Nqueue.get(block=True, timeout=0.01)
                    self.chunk = max(int(round(float(self.total) / 1000.)), 10)
                except Queue.Empty:
                    pass
                try:
                    hit, imgmax, imgmin, imgmed, peaks = self.results.get(block=False, timeout=None)
                    self.hit += hit
                    self.out += 1
                    percent = (float(self.out) / (self.total)) * 100.
                    hitrate = (float(self.hit) / float(self.out)) * 100.
                    self.signals.Job.emit([percent, hitrate])
                    if self.out % self.chunk == 0:
                        s = '     %6.2f %%       %5.1f %%    %8.2f    %7.2f  %6.2f %4d  (%i out of %i images processed - %i hits)' % (
                            percent, hitrate, imgmax, imgmin, imgmed, peaks, self.out, self.total, self.hit)

                        if self.log is None:

                            self.print_function(s, end='\r')
                            sys.stdout.flush()
                        else:
                            self.print_function(s)


                except Queue.Empty:
                    break

    def displayFinalStats(self):
            self.t2 = time.time()
            if self.out == 0:
                finalMessage = 'Slow Down - NPC was not able to process a single frame !!!'
            else:
                finalMessage = '\n\nOverall, found %s hits in %s processed files --> %5.1f %% hit rate with a threshold of %s' \
                               '\nIt took %4.2f seconds to process %i images (i.e %4.2f images per second)' % (
                               self.hit,
                               self.out,
                               float(self.hit) / (self.out) * 100.,
                               self.options['threshold'],
                               self.t2 - self.t1,
                               self.out,
                               self.out / (self.t2 - self.t1))
            self.print_function(finalMessage)
            self.signals.Stop.emit(True)
# Not used anymore


class FileSentinel(multiprocessing.Process):
    def __init__(self, task_queue, total_queue, options):
        multiprocessing.Process.__init__(self)
        self.kill_received = False
        self.total_queue = total_queue
        self.tasks = task_queue
        self.options = options
        self.live = self.options['live']
        self.all = []
        self.total = 0
        self.chunk = 0
        self.h5path = None
        self.overload = 0

        #User Choice
        if 'h5' in self.options['file_extension']:
            self.load_queue = self.loadH5Queue
        else:
            self.load_queue = self.loadSsxQueue

    def loadSsxQueue(self):
        try:
            self.total += len(self.filenames)
            self.total_queue.put(self.total)
            for fname in self.filenames:
                self.tasks.put(fname, block=True, timeout=None)
            self.givePoisonPill()
        except KeyboardInterrupt:
            print("File Sentinel exited properly")
            return

    def loadH5Queue(self):

        #Looking for data path into h5, getting type and deducing data overload
        self.h5path, self.overload, self.type = self.geth5path(self.filenames)

        if self.options['background_subtraction'].lower() != 'none':
            self.type=np.float64

        if self.options['HitFile'] is None:
            for filename in self.filenames:
                #Log("[%s] Opening %s"%(self.name, filename))
                h5 = h5py.File(filename)
                try:
                    num_frames, res0, res1 = h5[self.h5path].shape
                    self.total += num_frames
                    task = (filename, self.h5path, self.overload, self.type, num_frames)
                    self.tasks.put(task, block=True, timeout=None)
                    self.total_queue.put(self.total)
                except KeyError:
                    continue
                except KeyboardInterrupt:
                    print("File Sentinel exited properly")
                    return

                h5.close()
        else:
            for filename in self.filenames:
                task = (filename, self.h5path, self.overload, self.type, self.options['HitFile'][filename])
                self.tasks.put(task, block=True, timeout=None)
                self.total += len(self.options['HitFile'][filename])

        self.total_queue.put(self.total)
        self.chunk = max(int(round(float(self.total) / 1000.)), 10)

        self.givePoisonPill()

    def visitor_func(self, name, node):
        if isinstance(node, h5py.Dataset):
            try:
                if node.shape[1] * node.shape[2] > 512 * 512:
                    return node.name
            except IndexError:
                return None

    def geth5path(self, fns):
        i = 0
        path = None
        while path is None:
            h5 = h5py.File(fns[i])
            i += 1
            path = h5.visititems(self.visitor_func)
            if path is not None:
                ty = h5[path].dtype
                try:
                    ovl = np.iinfo(ty).max
                except ValueError:
                    ovl = np.finfo(ty).max

                return path, ovl, ty

    def givePoisonPill(self):
        if not self.live:
            for i in range(self.options['cpus']):
                self.tasks.put(None)


    def run(self):
        try:
            if self.options['HitFile'] is None:
                self.filenames = get_filenames(self.options)
            else:
                self.filenames = self.options['HitFile'].keys()
            self.load_queue()
            if self.live:
                while True:
                    self.all += self.filenames
                    self.filenames = get_filenames(self.options, self.all)
                    if self.filenames:
                            self.load_ssx_queue()
                    time.sleep(10)
        except KeyboardInterrupt:
            print("File Sentinel exited properly")
            return


class MProcess(multiprocessing.Process):

    def __init__(self, task_queue, result_queue, options, detector, ai, MShemArray, name, npg=None):
        multiprocessing.Process.__init__(self)

        self.npg = npg
        self.hitsignal = Signals()
        self.name = multiprocessing.current_process().name
        self.kill_received = False
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.options = options
        self.detector = detector
        self.AzimuthalIntegrator = ai
        self.signal = True
        self.MShemArray = MShemArray
        self.Nhits = 0
        self.NFramesPerH5 = 100
        self.h5out = None



        #Defining ROI
        if self.options['roi'] == 'None' :
            self.xmax, self.ymax = self.detector.shape
            self.xmin, self.ymin = 0, 0
            self.ActiveROI = False

        else:
            y1, x1, y2, x2 = self.options['roi'].split()
            self.xmax = max(int(x1), int(x2))
            self.xmin = min(int(x1), int(x2))
            self.ymax = max(int(y1), int(y2))
            self.ymin = min(int(y1), int(y2))
            self.ActiveROI = True

        self.options['ROI_tuple'] = (self.xmin, self.xmax, self.ymin, self.ymax)
        self.roi = self.options['ROI_tuple']

        if self.options['background_subtraction'].lower() != 'none':
            self.type = np.float32
            self.SubtractBkg = True
        else:
            self.type = np.int32
            self.SubtractBkg = False

        self.mask = self.getMask()
        self.dark = self.getCorrection(self.options['dark'])

        self.data = np.zeros((self.xmax-self.xmin, self.ymax-self.ymin))

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
        while True:
            try:
                    next_task = self.task_queue.get()
                    if next_task is None:
                        self.exitProperly()
                        break
                    else:
                        self.task_queue.task_done()
                        self.isHit(next_task)


            except KeyboardInterrupt:
                self.exitProperly()
                return
        return

    def exitProperly(self):
        try:
            self.task_queue.task_done()
        except ValueError: pass

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


    def isHit(self,filename):

        try:
            self.img = fabio.open(filename)
        except AssertionError:
            time.sleep(1)
            self.img = fabio.open(filename)

        self.data = self.correctData(
                    self.img.data[self.xmin:self.xmax, self.ymin:self.ymax].astype(np.int32),
                    self.dark,
                    self.roi)

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
        masked = np.ma.array(self.data, mask=self.mask[self.xmin:self.xmax, self.ymin:self.ymax])
        #N = masked[masked > self.ovl].size
        #if N > 0: print("WARNING: Found %i overloaded pixels - You might want to check your mask" % N)

        # Hit Finding
        hit = int( np.count_nonzero(masked.compressed() > self.options['threshold']) >= self.options['npixels'])

        #Could delay that
        self.result_queue.put((hit, 1, filename))

        if len(self.options['output_formats'].split()) > 0 and hit > 0:
            if self.ActiveROI:
                self.data = self.correctData(self.img.data,
                                             self.dark,
                                             (0, self.detector.shape[0], 0, self.detector.shape[1]))

            self.saveHit(filename)




    def setOutputRoot(self, fname):
        self.root, self.extension = os.path.splitext(os.path.basename(fname))


    def saveHit(self, fname):

        self.setOutputRoot(fname)

        #TODO : Bragg Search here - Save to txt file or H5

        #Update Screen
        if str(self.name) == '0' and self.MShemArray is not None:
            n = self.data.shape[0]
            m = self.data.shape[1]
            self.MShemArray[:] = self.data.reshape((1,n*m))[0][:]
        

        self.saveFormat = {'edf':['EDF','edf',self.saveEdf],
                           'cbf':['CBF','cbf',self.saveCbf],
                           'hdf5': ['HDF5','h5',self.saveH5],
                           'pickles':['PICKLES','pickle',self.savePickle]}

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
        #else: print('Ahhhh')
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
        if 'eiger' in self.detector.name.lower(): ovl = self.ovl
        return ovl

    def OnStop(self):
        try:
            self.signal = False
        except:
            return


class MProcessEiger(MProcess):
    def __init__(self, task_queue, result_queue, options, detector, AzimuthalIntegrator, MShemArray, name, npg=None):
        MProcess.__init__(self,  task_queue, result_queue, options, detector, AzimuthalIntegrator, MShemArray, name, npg)
        self.h5 = None
        self.h5_filename = None
        self.NFramesPerH5 = 100
        self.h5out = None
        self.dset = None
        self.data = np.zeros((self.xmax - self.xmin, self.ymax - self.ymin), dtype=self.type)
        self.count = 0

    def isHit(self,task):

        filename, self.group, self.ovl, self.type, N = task
        self.h5 = h5py.File(filename,'r')

        if self.options['HitFile'] is not None:
            iterable = [int(x) for x in N]
        else: iterable = range(0,N)
        for i in iterable:
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
                        restore_mask=True)[0][self.xmin:self.xmax,self.ymin:self.ymax]

            else:
                self.data = self.correctData(self.h5[self.group][i,self.xmin:self.xmax,self.ymin:self.ymax].astype(np.int32),
                                         self.dark,
                                         self.options['ROI_tuple'])
            
            #BKG Sub using mask

            #Masking Array
            
            masked = np.ma.array(self.data,
                                 mask=self.mask[self.xmin:self.xmax, self.ymin:self.ymax])

            #N=masked[masked > self.ovl].size
            #if N > 0: print("WARNING: Found %i overloaded pixels - You might want to check your mask"%N)

            #Hit Finding
            hit = int( np.count_nonzero(masked.compressed() > self.options['threshold']) >= self.options['npixels'])

            self.result_queue.put((hit, 1, '%s //%i'%(filename,i)))

            if len(self.options['output_formats'].split()) > 0 and hit > 0:
                if self.options['roi'].lower() != 'none':
                    self.data = self.correctData(self.h5[self.group][i,::],
                                                 self.dark,
                                                 (0,self.detector.shape[0],0,self.detector.shape[1]))

                self.saveHit('%s_%i'%(filename,i))
                self.count += 1
        self.h5.close()
        return


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
