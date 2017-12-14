from __future__ import print_function
import sys
import time
import multiprocessing
import os
try:
    import Queue
except ImportError:
    import queue as Queue
import pyFAI
import pyFAI.detectors
import numpy as np
import h5py
import fabio
from .Azimuthal_Integrator import AI
from . import utils
from PyQt4 import QtCore
from multiprocessing import Event
from .ZmqSockets import ZMQPush
import zmq, json

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
            TotalN=0
            for filename in self.filenames:
                #print(filename)
                #Log("[%s] Opening %s"%(self.name, filename))
                h5 = h5py.File(filename,'r')
                try:
                    num_frames, res0, res1 = h5[self.h5path].shape
                    if self.options['shootntrap']:

                        idx_start = TotalN % self.options['nperposition'] + self.options['nempty']
                        idx = [i for i in range(idx_start,num_frames,self.options['nperposition'])]
                        self.total += len(idx)
                        TotalN += num_frames

                    else:
                        self.total += num_frames
                        idx = num_frames
                    task = (filename, self.h5path, self.overload, self.type, idx)
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
                task = (filename, self.h5path, self.overload, self.type, [int(x) for x in self.options['HitFile'][filename]])
                self.tasks.put(task, block=True, timeout=None)
                self.total += len(self.options['HitFile'][filename])

        self.total_queue.put(self.total)
        print(self.total)
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
                self.filenames = utils.get_filenames(self.options)
            else:
                self.filenames = self.options['HitFile'].keys()
            self.load_queue()
            if self.live:
                while True:
                    self.all += self.filenames
                    self.filenames = utils.get_filenames(self.options, self.all)
                    if self.filenames:
                            self.load_queue()
                    time.sleep(10)
        except KeyboardInterrupt:
            print("File Sentinel exited properly")
            return


class Signals(QtCore.QObject):
    Stop =  QtCore.pyqtSignal(bool)
    Job = QtCore.pyqtSignal(tuple)


class DataProcessing(object):
    def __init__(self, options):
        # Common part
        self.options = options
        self.experiment = self.options['experiment']
        self.init_detector()
        if self.options['background_subtraction'].lower() != 'none':
            self.ai = AI(self.options, self.detector)
        else: self.ai = None


    def init_detector(self):
        # This is as messy as hell !!!
        self.detector = None
        try:
            detector_name = self.options['detector']
            self.detector = pyFAI.detectors.Detector.factory(detector_name)
        except RuntimeError:
            print("This detector is not implemented in pyFAI / NPC - Please contact us")
            sys.exit(1)
        # elif self.options['experiment'] == 'SFX_SACLA':
        #        from NPC.Detectors import MPCCD
        #        self.detector = MPCCD()
        # elif self.options['experiment'] == 'SFX_LCLS':
        #        from NPC.Detectors import CSPAD
        #        self.detector = CSPAD()


class StatsManager(object):

    def __init__(self, options, resultsQueue ):
        self.options = options
        self.resultsQueue = resultsQueue
        #self.socket = ZMQPush(host='127.0.0.1',port=5556,flags=zmq.NOBLOCK, verbose=False)
        self.initTxtFiles()
        self.t1 = time.time()
        #self.signals = Signals()
        self.chunk = 20
        self.total = 0
        self.processed = 0
        self.hits = 0

    def flush(self):
        percent = (float(self.processed) / self.total) * 100.
        hitrate = (float(self.hits) / float(self.processed)) * 100.
        #self.signals.Job.emit((self.total, self.processed, self.hits))
        s = '     %6.2f %%       %5.1f %%    (%i out of %i images processed - %i hits)' % (
                percent, hitrate, self.processed, self.total, self.hits)
        #if self.log is None:
        print(s, end='\r')
        sys.stdout.flush()
        #else:
        #    self.print_function(s)

    def initTxtFiles(self):
        OutputFileName = os.path.join(self.options['output_directory'], 'NPC_run%s' % self.options['num'].zfill(3),
                                      '%s_%s' % (self.options['filename_root'], self.options['num'].zfill(3)))
        self.outTxtHit = open('%s.txt' % OutputFileName, 'w')
        self.outTxtRej = open('%s_rejected.txt' % OutputFileName, 'w')

    def getFinalResults(self):
        #self.signals.Job.emit((self.total, self.processed, self.hits))
        self.options['total'] = self.total
        self.options['processed'] = self.processed
        self.options['hit'] = self.hits
        self.t2 = time.time()
        if self.processed == 0:
            finalMessage = 'Slow Down - NPC was not able to process a single frame !!!'
        else:
            finalMessage = '\n\nOverall, found %s hits in %s processed files --> %5.1f %% hit rate with a threshold of %s\nIt took %4.2f seconds to process %i images (i.e %4.2f images per second)' % (
                self.hits,
                self.processed,
                (float(self.hits) / (self.processed) * 100.),
                self.options['threshold'],
                (self.t2 - self.t1), self.hits, self.processed / (self.t2 - self.t1))
        print(finalMessage)
        self.outTxtHit.close()
        self.outTxtRej.close()
        with open(self.options['json_file'],'w') as outfile:
            print(outfile)
            json.dump(self.options, outfile)
        self.socket.close()
        #self.signals.Stop.emit(True)

    def getResults(self):
        Nhit, N, fnsHit, fnsRej, path = self.resultsQueue.get(block=False, timeout=None)
        self.processed += N
        self.hits += Nhit

        if fnsHit: self.saveHits(fnsHit, path)
        if fnsRej: self.outTxtRej.write(fnsRej)
        if self.processed % self.chunk == 0 and self.processed > 0:
            self.flush()

    def saveHits(self, fnsHit, path):
        fn = fnsHit.split('\n')[0].strip()
        if path is None:
            index = None
        else:
            fn, index = fn.strip().split('//')
        self.outTxtHit.write(fnsHit)
        self.send(fn, path, index)

    def send(self, fn, path, index):
        d = {}
        d['total'] = self.total
        d['processed'] = self.processed
        d['hit'] = self.hits
        d['index'] = index
        d['path'] = path
        d['fn'] = fn
        try:
            self.socket.send(d)
        except:
            pass

# Changed in the scope of NPC
class DataProcessingMPI(DataProcessing):
        def __init__(self, options, log=None, npg=None):
            DataProcessing.__init__(self, options)
            
            try:
                from mpi4py import MPI
            except RuntimeError:
                print('If you want to use the MPI option, please install OpenMPI and mpi4py')
                sys.exit(1)
            self.MPI = MPI
            self.comm = MPI.COMM_WORLD
            self.rank = self.comm.rank
            self.size = self.comm.size



            if self.rank == 0:
                utils.startup(options)



            self.HitFinder = HitFinder(self.options, self.detector, self.ai)

            self.t1 = time.time()
            self.total = 0
            self.hit = 0
            self.out = 0
            self.signal = True
            self.max_proj = np.zeros(self.detector.shape, np.int32)
            self.avg = np.zeros_like(self.max_proj)

            self.run_mapping = {'SSX' : self.run_ssx, 'SFX_SACLA' : self.run_sacla, 'SFX_LCLS' : self.run_lcls}
            self.run_mapping[self.options['experiment']]()


        def get_filenames(self):
            if self.rank == 0:
                self.filenames = self.get_filenames_mapping[self.experiment](self.options)
                for i in range(1, self.size): self.comm.send(self.filenames, dest=i)

            if self.rank != 0: self.filenames = self.comm.recv(source=0)

        def run_ssx(self):
            self.get_filenames()
            if 'eiger' in self.options['detector'].lower(): self.run_eiger()
            else:
                self.total = len(self.filenames)
                for idx in range(self.rank,self.total,self.size):
                    fname = self.filenames[idx]
                    self.HitFinder.data = fabio.open(fname).data
                    hit, imgmax, imgmin, imgmed, peaks, working = self.HitFinder.get_hit(fname)
                    if hit == 1:
                        self.update_results(working)
                self.get_final_stats()

        def run_eiger(self):

            self.get_filenames()
            for filename in self.filenames:

                h5=h5py.File(filename)
                for key in h5['entry']:
                    if 'data' in key:
                        num_frames, res0, res1 = h5['entry/{}'.format(key)].shape
                        self.total += num_frames
                        myindexes = [j for j in range(num_frames) if (j+self.rank) % self.size == 0]
                        for index in myindexes:
                            self.HitFinder.data[:] = h5['entry/%s'%group][index,::]
                            hit, imgmax, imgmin, imgmed, peaks,working = self.HitFinder.get_hit()
                            if hit == 1:
                                self.update_results(working)
                h5.close()
            self.get_final_stats()

        def shutDown(self):
            self.exit.set()

        def getStats(self):
            while True or self.statsManager.processed != self.statsManager.total:
                try:
                    self.statsManager.total = self.N_queue.get(block=False, timeout=None)
                    self.statsManager.chunk = max(int(round(float(self.statsManager.total) / 1000.)), 20)
                except Queue.Empty:
                    pass

                try:
                    self.statsManager.getResults()

                except Queue.Empty:
                    break

        def startFS(self):
            self.FS.daemon = True
            self.FS.start()

        def update_results(self,working):
                self.hit += 1
                self.avg += working
                maxids = np.where(working > self.max_proj)
                self.max_proj[maxids] = working[maxids]

        def get_final_stats(self):
            t2 = time.time()
            t_final = self.comm.reduce(t2-self.t1, op=self.MPI.SUM,root = 0)
            hit_final = self.comm.reduce(self.hit, op=self.MPI.SUM,root = 0)
            if self.rank == 0:
                print('\nOverall, found %s hits in %s files --> %5.1f %% hit rate with a threshold of %s' % (
                        hit_final, self.total, ((float(hit_final) / (self.total)) * 100.), self.options['threshold']))
                t_final = t_final / self.size
                print("Time to process {} frames on {} procs: {:4.2f} seconds (i.e {:4.2f} frames per second)".format(self.total,self.size,t_final,self.total/t_final))
                avg_final = np.zeros_like(self.max_proj)
                cleanmax = np.zeros_like(self.max_proj)
                max_proj_final = np.zeros_like(self.max_proj)
            else :
                avg_final = None
                max_proj_final = None
            self.comm.Reduce([self.avg,self.MPI.INT], [avg_final, self.MPI.INT], op=self.MPI.SUM,root = 0)
            self.comm.Reduce([self.max_proj,self.MPI.INT], [max_proj_final, self.MPI.INT], op=self.MPI.MAX,root = 0)

            if self.rank == 0 and hit_final > 0:
                avg_final = self.avg / hit_final
                cleanmax = max_proj_final - self.avg
                self.saveMaxProj(cleanmax,max_proj_final,avg_final)

        def saveMaxProj(self,cleanmax,max_proj_final,avg_final):

            output_directory=self.options['output_directory']
            num = str(self.options['num']).zfill(3)
            for output_format in self.options['output_formats'].split():
                maxproj_directory = os.path.join(output_directory,"%s_%s"%(output_format.upper(),num),'MAX')

                for data,root_name in ((cleanmax,'cleanmax'), (max_proj_final,'maxproj'), (avg_final,'avg')):
                    if output_format == 'hdf5':
                        output_filename = os.path.join(maxproj_directory,'%s.h5'%(root_name))
                        image = h5py.File(output_filename)
                        image.create_dataset("data", data=data, compression="gzip")
                        image.close()

                    elif output_format == 'pickles':
                        pass

                    else:
                        image=utils.get_class('fabio.%simage'%output_format,'%simage'%output_format)(data=data)
                        output_filename = os.path.join(maxproj_directory,'%s.%s'%(root_name,output_format))
                        image.write(output_filename)


class DataProcessingMultiprocessing(DataProcessing):

    def __init__(self, options, log=None, npg = None):
        DataProcessing.__init__(self, options)
        self.log = log
        self.npg = npg
        self.signals = Signals()
        self.exit = Event()

        utils.startup(self.options, print)
        self.tasks = multiprocessing.JoinableQueue(maxsize=10000)
        self.N_queue = multiprocessing.Queue()
        self.results = multiprocessing.Queue()
        self.FS = FileSentinel(self.tasks, self.N_queue, self.options)

        if 'h5' in self.options['file_extension'].lower():
            from .MultiProcess import MProcessEiger as MProcess
        else: from .MultiProcess import MProcess

        self.consumers = [
            MProcess(self.tasks, self.results, self.options, self.detector,
                          self.ai, None, name=str(i)) for i in range(self.options['cpus'])]

        self.statsManager = StatsManager(self.options, self.results)

    def run(self):
        self.startMP()
        self.startFS()

        i=0
        if self.options["live"]:
            try:
                while not self.exit.is_set():
                    self.getStats()
                    i +=1
            except KeyboardInterrupt:
                print("\n\nCtrl-c received! --- Aborting and trying not to compromising results...")

        else:
            while (self.statsManager.processed != self.statsManager.total or self.statsManager.processed == 0) and not self.exit.is_set():
                try:
                    self.getStats()
                except KeyboardInterrupt:
                    print("\n\nCtrl-c received --- Aborting and trying not to compromising results...")
                    break

        self.statsManager.getFinalResults()

    def shutDown(self):
        self.exit.set()

    def getStats(self):
        while True or self.statsManager.processed != self.statsManager.total:
            try:
                self.statsManager.total = self.N_queue.get(block=False, timeout=None)
                self.statsManager.chunk = max(int(round(float(self.statsManager.total) / 1000.)), 20)
            except Queue.Empty:
                pass

            try:
                self.statsManager.getResults()

            except Queue.Empty:
                break

    def startFS(self):
        self.FS.daemon = True
        self.FS.start()

    def startMP(self):
        """ Start as many processes as set by the user
    	"""
        for w in self.consumers:
            w.start()

    #def startDisplay(self):
    #    self.DR = DisplayResults(self.N_queue, self.results, self.options, self.log)
    #    self.DR.start()

    # def saveMaxProj(self,cleanmax,max_proj_final,avg_final):
    #         #Not used anymore
    #         outputDirectory=self.options['output_directory']
    #         num = str(self.options['num']).zfill(3)
    #         for outputFormat in self.options['output_formats'].split():
    #             maxproj_directory = os.path.join(outputDirectory,"%s_%s"%(outputFormat.upper(),num),'MAX')
    #             for data,root_name in ((cleanmax,'cleanmax'), (max_proj_final,'maxproj'), (avg_final,'avg')):
    #                 if outputFormat == 'hdf5':
    #                     output_filename = os.path.join(maxproj_directory,'%s.h5'%(root_name))
    #                     image = h5py.File(output_filename,'w')
    #                     image.create_dataset("data", data=data, compression="gzip")
    #                     image.close()
    #                 elif outputFormat == 'pickles':
    #                     pass
    #                 else:
    #                     image=utils.get_class('fabio.%simage'%outputFormat,'%simage'%outputFormat)(data=data)
    #                     output_filename = os.path.join(maxproj_directory,'%s.%s'%(root_name,outputFormat))
    #                     image.write(output_filename)

# ===================================================================================================================
if __name__ == '__main__':
    options_EIGER = {'detector': 'Eiger4M',
                    'experiment': 'SSX',
                    'detector_distance': 100,
                    'beam_x': 502,
                    'beam_y': 515,
                    'wavelength': 0.832,
                    'output_directory': '.',
                    'num': '1',
                    'output_formats': '',
                    'data': '/Users/coquelleni/PycharmProjects/NPC_DATA',
                    'filename_root': 'lyscryo',
                    'file_extension': '.h5',
                    'HitFile': utils.parseHits('/Users/coquelleni/PycharmProjects/NanoPeakCell_0.3.1/NPC/lyscryo_01.txt'),
                    #'HitFile': None,
                    'cpus': 3,
                    'threshold': 10,
                    'npixels': 30,
                    'mask': 'None',
                    'dark': 'none',
                    'live': False,
                    'background_subtraction': 'None',
                    'bragg_search': False,
                    'roi': '0 0 1000 1000',

               }

    options_SSX = {
                'detector': 'Pilatus6M',
                'experiment': 'SSX',
                'detector_distance': 100,
                'output_directory': '.',
                'num': '1',
                'output_formats': '',
                'data': '/Users/coquelleni/PycharmProjects/tmp',
                'filename_root': 'b3rod',
                'file_extension': '.cbf',
                'randomizer': 0,
                'cpus': 8,
                'threshold': 40,
                'npixels': 3,
                'background_subtraction': 'None',
                'bragg_search': True,
                'bragg_threshold': 200,
                'mask': 'None',
                'dark': 'none',
                'live': False,
                #'roi': 'None',
                'roi':  '0 0 1000 1000',
                'distance': 123,
                'wavelength': 1.23,
                'beam_y': 800,
                'beam_x': 1200

               }
    #Test = DataProcessingMultiprocessing(options_SSX)
    Test = DataProcessingMultiprocessing(options_EIGER)
    Test.run()
    #Test = DataProcessing_MPI(options_SSX)
    #Test = DataProcessing_MPI(options_EIGER)
