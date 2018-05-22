from __future__ import print_function
import sys
import time
import multiprocessing
import os
try:
    import Queue
except ImportError:
    import queue as Queue
import numpy as np
import h5py
from .Azimuthal_Integrator import AI
from . import utils
from multiprocessing import Event
from NPC.NPC_routines import InitDetector
import json

class FileSentinel(multiprocessing.Process):
    def __init__(self, task_queue, total_queue, options):
        multiprocessing.Process.__init__(self)
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




class DataProcessing(object):
    def __init__(self, options):
        # Common part
        self.options = options
        self.experiment = self.options['experiment']
        self.detector = InitDetector(self.options)
        if self.options['background_subtraction'].lower() != 'none':
            self.ai = AI(self.options, self.detector)
        else: self.ai = None


class StatsManager(object):

    def __init__(self, options, resultsQueue ):
        self.options = options
        self.resultsQueue = resultsQueue
        #self.socket = ZMQPush(host='127.0.0.1',port=5556,flags=zmq.NOBLOCK, verbose=False)
        self.initTxtFiles()
        self.t1 = time.time()
        self.chunk = 20
        self.total = 0
        self.processed = 0
        self.hits = 0

    def flush(self):
        percent = (float(self.processed) / self.total) * 100.
        hitrate = (float(self.hits) / float(self.processed)) * 100.
        s = '     %6.2f %%       %5.1f %%    (%i out of %i images processed - %i hits)' % (
                percent, hitrate, self.processed, self.total, self.hits)
        print(s, end='\r')
        sys.stdout.flush()

    def initTxtFiles(self):
        OutputFileName = os.path.join(self.options['output_directory'], 'NPC_run%s' % self.options['num'].zfill(3),
                                      '%s_%s' % (self.options['filename_root'], self.options['num'].zfill(3)))
        self.outTxtHit = open('%s.txt' % OutputFileName, 'w')
        self.outTxtRej = open('%s_rejected.txt' % OutputFileName, 'w')

    def getFinalResults(self):
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

            json.dump(self.options, outfile)
        #self.socket.close()

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


class DataProcessingMultiprocessing(DataProcessing):

    def __init__(self, options, log=None):
        DataProcessing.__init__(self, options)
        self.log = log
        self.exit = Event()

        utils.startup(self.options)
        # First queue - Send the jobs
        self.tasks = multiprocessing.JoinableQueue(maxsize=10000)
        # Second one - Send the number of images to process
        self.N_queue = multiprocessing.Queue()
        # Third one - the results
        self.results = multiprocessing.Queue()

        # Process to look after the files
        self.FS = FileSentinel(self.tasks, self.N_queue, self.options)

        # Real workers...
        if 'h5' in self.options['file_extension'].lower():
            from .MultiProcess import MProcessEiger as MProcess
        else: from .MultiProcess import MProcess
        self.consumers = [ MProcess(self.tasks, self.results, self.options, self.ai, self.detector, name=str(i)) for i in range(self.options['cpus'])]
        # Some stats
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
                self.statsManager.chunk = max(int(self.statsManager.total / 1000.), 20)
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
