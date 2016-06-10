import sys
import time
import multiprocessing
import os
import Queue
import pyFAI
import pyFAI.detectors
import numpy as np
import h5py
import fabio
from NPC.Azimuthal_Integrator import AI
import NPC.utils as utils

class DataProcessing(object):
    def __init__(self, options):
        # Common part
        self.options = options
        self.experiment = self.options['experiment']
        self.init_detector()
        self.ai = AI(self.options, self.detector)
        self.get_filenames_mapping = {'SSX': utils.get_filenames, 'SFX_SACLA': utils.get_files_sacla}

    def init_detector(self):
        self.detector = None
        if self.options['experiment'] == 'SSX':
            if self.options['detector'] == 'eiger4m_fake':
                from NPC.Detectors import Eiger_4M_fake
                self.detector = Eiger_4M_fake()
                return
            if self.options['detector'].lower() == 'frelon':
                from NPC.Detectors import Frelon
                self.detector = Frelon()
                return

            try:
                detector_name = self.options['detector']
                self.detector = pyFAI.detectors.Detector.factory(detector_name)
            except RuntimeError:
                "This detector is not implemented in pyFAI - Please contact us"
                sys.exit(1)

        elif self.options['experiment'] == 'SFX_SACLA':
                from NPC.Detectors import MPCCD
                self.detector = MPCCD()
        elif self.options['experiment'] == 'SFX_LCLS':
                from NPC.Detectors import CSPAD
                self.detector = CSPAD()


class DataProcessing_MPI(DataProcessing):

        def __init__(self, options):
            DataProcessing.__init__(self, options)
            
            try:
                from mpi4py import MPI
            except RuntimeError:
                print 'If you want to use the MPI option, please install OpenMPI and mpi4py'
                #print 'Switching back to Multiprocessing'

                sys.exit(1)
            self.MPI = MPI
            self.comm = MPI.COMM_WORLD
            self.rank = self.comm.rank
            self.size = self.comm.size

            if self.rank == 0:
                utils.startup(options)
            self.HitFinder = HitFinder(self.options, self.detector, self.ai)
            # Deal with dark
            # self.calculate_mask()

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
                for idx in xrange(self.rank,self.total,self.size):
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
                        myindexes = [j for j in xrange(num_frames) if (j+self.rank) % self.size == 0]
                        for index in myindexes:
                            self.HitFinder.data[:] = h5['entry/%s'%group][index,::]
                            hit, imgmax, imgmin, imgmed, peaks,working = self.HitFinder.get_hit()
                            if hit == 1:
                                self.update_results(working)
                h5.close()
            self.get_final_stats()

        def run_sacla(self):
            self.get_filenames()
            for filename in self.filenames:
            #if self.signal:
                h5=h5py.File(filename)
                run = h5.keys()[0]
                tags = h5['%s/event_info/tag_number_list'%run][:]
                if self.rank == 0: self.total += len(tags)
                mytags = [tags[j] for j in range(len(tags)) if (j+self.rank)%self.size==0]
                for tag in mytags:
                    self.HitFinder.data = h5['%s/detector_2d_assembled_1/tag_%s/detector_data'%(run,tag)][:]
                    hit, imgmax, imgmin, imgmed, peaks,working = self.HitFinder.get_hit((run,tag))
                    if hit == 1:
                        self.update_results(working)
                h5.close()
            self.get_final_stats()
            self.save_maxproj()

        def run_lcls(self):
            ds = DataSource('exp=%s:run=%s:idx'%(self.options['experiment'],self.options['run']))
            for run in ds.runs():
                self.options['runnumber'] = run.run()
                times = run.times()
                if self.rank == 0: total += len(times)
                mytimes = [times[i] for i in xrange(len(times)) if (i+self.rank)%size == 0]
                for i in xrange(len(mytimes)):
                    evt = run.event(mytimes[i])
                    id = evt.get(EventId).time()
                    img = evt.get(ndarray_float64_2,Source('DetInfo(CxiDg4.0:Cspad.0)'),'reconstructed') - dark
                    self.HitFinder.data = np.transpose(img.astype(np.int64))
                    hit, imgmax, imgmin, imgmed, peaks,working = self.HitFinder.get_hit(id)
                    if hit == 1:
                        self.update_results(working)
            self.get_final_stats()


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
                print '\nOverall, found %s hits in %s files --> %5.1f %% hit rate with a threshold of %s' % (
                        hit_final, self.total, ((float(hit_final) / (self.total)) * 100.), self.options['threshold'])
                t_final = t_final / self.size
                print "Time to process {} frames on {} procs: {:4.2f} seconds (i.e {:4.2f} frames per second)".format(self.total,self.size,t_final,self.total/t_final)
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
                self.save_maxproj(cleanmax,max_proj_final,avg_final)

        def save_maxproj(self,cleanmax,max_proj_final,avg_final):

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


class DataProcessing_multiprocessing(DataProcessing):

    def __init__(self,options):

        DataProcessing.__init__(self, options)
        utils.startup(self.options)
        self.live = self.options['live']
        self.run()

    def run(self):
        from MultiProcess import MProcess, FileSentinel
        self.tasks = multiprocessing.JoinableQueue(maxsize=10000)
        self.N_queue = multiprocessing.Queue()
        self.results = multiprocessing.Queue()

        self.MProcess = MProcess
        self.start_mp()
        self.FileSentinel = FileSentinel
        self.start_FS()

        self.find_hits()

    def start_FS(self):
        self.FS = self.FileSentinel(self.tasks, self.N_queue, self.options, self.detector, self.ai)
        self.FS.start()

    def start_mp(self):
        """ Start as many processes as set by the user
    	"""
        self.consumers = [
            self.MProcess(self.tasks, self.results, self.options, self.detector,
                              self.ai) for i in xrange(self.options['cpus'])]
        for w in self.consumers:
            w.start()

    def find_hits(self):
        self.t1 = time.time()
        self.hit = 0
        self.out = 0
        self.total = 0


        if self.live:
            while True:
              self.get_results()
              time.sleep(0.1)
        else:
          while self.out != self.total or self.out == 0:
            self.get_results()
          self.get_final_stats()


    def get_results(self):

            while True:
                try:
                    self.total = self.N_queue.get(block=True, timeout=0.01)
                except:
                    pass

                self.chunk = self.chunk = max(int(round(float(self.total) / 1000.)), 10)

                try:
                    hit, imgmax, imgmin, imgmed, peaks = self.results.get(block=False, timeout=None)
                    self.hit += hit
                    self.out += 1
                    percent = (float(self.out) / (self.total)) * 100.
                    hitrate = (float(self.hit) / float(self.out)) * 100.

                    if self.out % self.chunk == 0:
                        print('     %6.2f %%       %5.1f %%    %8.2f    %7.2f  %6.2f %4d  (%i out of %i images processed - %i hits) \r') % (
                                     percent,      hitrate,    imgmax, imgmin, imgmed, peaks, self.out, self.total, self.hit),
                        sys.stdout.flush()

                except Queue.Empty:
                    break

    def get_final_stats(self):

        print('\n\nOverall, found %s hits in %s files --> %5.1f %% hit rate with a threshold of %s')% (
                   self.hit, self.total, (float(self.hit) / (self.total) * 100.), self.options['threshold'])
        self.t2 = time.time()
        print("It took %4.2f seconds to process %i images (i.e %4.2f images per second)")% (
            (self.t2 - self.t1), self.total, self.total / (self.t2 - self.t1))

        #if self.hit > 0:
        #    self.avg = self.avg / self.hit
        #    self.cleanmax = self.max_proj - self.avg
        #    self.save_maxproj(self.cleanmax,self.max_proj,self.avg)

    def save_maxproj(self,cleanmax,max_proj_final,avg_final):

            output_directory=self.options['output_directory']
            num = str(self.options['num']).zfill(3)

            for output_format in self.options['output_formats'].split():
                maxproj_directory = os.path.join(output_directory,"%s_%s"%(output_format.upper(),num),'MAX')
                for data,root_name in ((cleanmax,'cleanmax'), (max_proj_final,'maxproj'), (avg_final,'avg')):
                    if output_format == 'hdf5':
                        output_filename = os.path.join(maxproj_directory,'%s.h5'%(root_name))
                        image = h5py.File(output_filename,'w')
                        image.create_dataset("data", data=data, compression="gzip")
                        image.close()

                    elif output_format == 'pickles':
                        pass

                    else:
                        image=utils.get_class('fabio.%simage'%output_format,'%simage'%output_format)(data=data)
                        output_filename = os.path.join(maxproj_directory,'%s.%s'%(root_name,output_format))
                        image.write(output_filename)

#===================================================================================================================
if __name__ == '__main__':
    options_EIGER = {'detector': 'Eiger4M',
                    'experiment': 'SSX',
                    'detector_distance': 100,
                    'beam_x': 502,
                    'beam_y': 515,
                    'wavelength': 0.832,
                    'output_directory': '.',
                    'num': '1',
                    'output_formats': 'hdf5',
                    'data': '/Users/nico/IBS2013/EIGER',
                    'filename_root': 'series_100_master',
                    'file_extension': '.h5',
                    'randomizer': 100,
                    'mask': 'none',
                    'cpus': 1,
                    'threshold': 10,
                    'npixels': 30,
                    'background_subtraction': 'None',
                    'bragg_search': False

               }
    options_SACLA = {
               'experiment': 'SFX_SACLA',
               'detector_distance': 100,
               'beam_x': 502,
               'beam_y': 515,
               'wavelength': 0.832,
               'output_directory': '.',
               'num': 1,
               'output_formats': '',
               'data': '/Users/nico/IBS2013/Projects/SERIALX/IRISFP',
               'root': 'shot',
               'file_extension': '.h5',
               'randomizer': False,
               'runs': '1-2',
               'cpus': 1,
               'threshold': 1000,
               'npixels': 100,
               'background_subtraction': 'None',
               'bragg_search': False,
               'mask': '/Users/nico/Sacla_mask_ones.h5'
               }

    options_SSX = {
                'detector': 'Pilatus6M',
                'experiment': 'SSX',
                'detector_distance': 100,
                'beam_x': 502,
                'beam_y': 515,
                'wavelength': 0.832,
                'output_directory': '.',
                'num': '1',
                'output_formats': 'hdf5',
                'data': '/Users/coquelleni/PycharmProjects/tmp',
                'filename_root': 'b3rod',
                'file_extension': '.cbf',
                'randomizer': 0,
                'cpus': 8,
                'threshold': 40,
                'npixels': 3,
                'background_subtraction': 'None',
                'bragg_search': False,
                'mask': 'None',
                'dark': 'none',
                'live': False,
                #'ROI': 'None'
                'ROI':  '1257 1231 2527 2463'
               }
    Test = DataProcessing_multiprocessing(options_SSX)
    #Test = DataProcessing_multiprocessing(options_SACLA)
    #Test = DataProcessing_multiprocessing(options_EIGER)
    #Test = DataProcessing_MPI(options_SSX)
    #Test = DataProcessing_MPI(options_LCLS)
    #Test = DataProcessing_MPI(options_SACLA)
    #Test = DataProcessing_MPI(options_EIGER)
