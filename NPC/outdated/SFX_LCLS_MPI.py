from NPC.HitFinder_class import HitFinder

try:
    from wx.lib.pubsub import pub
except ImportError:
    from pubsub import pub

import time
from mpi4py import MPI
import pyFAI
import pyFAI.detectors
import numpy as np
from psana import *

comm = MPI.COMM_WORLD
rank = comm.rank
size = comm.size


class main(object):
    def __init__(self, options):

        self.options = options
        detector_name = options['detector']
        self.detector = pyFAI.detectors.Detector.factory(detector_name)
        self.ai = AI(self.options, self.detector)
        self.HitFinder = HitFinder(self.options, self.detector, self.ai)
        # Deal with dark
        # self.calculate_mask()
        self.find_hits()


    #----------------------------------------------
    def find_hits(self):
        t1 = time.time()
        self.hit_counter = 0
        self.out = 0
        self.signal = True

        self.HitFinder.dark = fabio.open('/reg/d/psdm/cxi/cxig7414/scratch/nico/dark_cxig7414_r0001.edf').data
        max_proj = np.zeros(self.detector.shape, np.int32)
        avg = np.zeros_like(max_proj)

        ds = DataSource('exp=%s:run=%s:idx'%(self.options['experiment'],self.options['run']))
        self.total = 0
        for run in ds.runs():
            self.dark = None
            self.options['runnumber'] = run.run()
            times = run.times()
            if rank == 0: total += len(times)
            mytimes = [times[i] for i in xrange(len(times)) if (i+rank)%size == 0]
            for i in xrange(len(mytimes)):
                evt = run.event(mytimes[i])
                id = evt.get(EventId).time()
                img = evt.get(ndarray_float64_2,Source('DetInfo(CxiDg4.0:Cspad.0)'),'reconstructed') - dark
                self.HitFinder.data = np.transpose(img.astype(np.int32))
                self.hit, self.imgmax, self.imgmin, self.imgmed,  self.peaks,  self.data = self.HitFinder.get_hit()
                if self.hit == 1:
                    self.hit_counter += 1
                    avg += self.data
                    # Use maximum of two arrays, element wise
                    maxids = np.where(self.data > max_proj)
                    max_proj[maxids] = self.data[maxids]


        t2 = time.time()
        t_final = comm.reduce(t2-t1, op=MPI.SUM,root = 0)
        hit_final = comm.reduce(self.hit_counter, op=MPI.SUM,root = 0)

        if rank == 0:
              print '\nOverall, found %s hits in %s files --> %5.1f %% hit rate with a threshold of %s' % (
                  hit_final, self.total, ((float(hit_final) / (self.total)) * 100.), self.options['threshold'])
              t_final = t_final / size
              print "Time to process {} frames on {} procs: {:4.2f} seconds (i.e {:4.2f} frames per second)".format(self.total,size,t_final,self.total/t_final)
              avg_final = np.zeros_like(max_proj)
              cleanmax = np.zeros_like(max_proj)
              max_proj_final = np.zeros_like(max_proj)
        else :
            avg_final = None
            max_proj_final = None
        comm.Reduce([avg,MPI.INT], [avg_final, MPI.INT], op=MPI.SUM,root = 0)
        comm.Reduce([max_proj,MPI.INT], [max_proj_final, MPI.INT], op=MPI.MAX,root = 0)

        if rank == 0:
            avg_final /=  float(hit_final)
            cleanmax = max_proj_final - avg_final


#To Move to bkg sub
class AI():
    """ This class instantitiates an azimutal integrator object
        from pyFAI. This object will then be used to perform
	    background subtraction.
    """

    def __init__(self, options, detector):
        self.detector = detector
        self.psx = self.detector.pixel1
        self.psy = self.detector.pixel2
        self.resolution = self.detector.shape

        self.distance = options['detector_distance'] / 1000.
        self.bcx = options['beam_y'] * self.psx
        self.bcy = options['beam_x'] * self.psy
        self.wl = options['wavelength']

        self.ai = pyFAI.AzimuthalIntegrator(dist=self.distance,
                                            poni1=self.bcx,
                                            poni2=self.bcy,
                                            rot1=0,
                                            rot2=0,
                                            rot3=0,
                                            pixel1=self.psx,
                                            pixel2=self.psy,
                                            splineFile=None,
                                            detector=self.detector,
                                            wavelength=self.wl)


    def test(self):
        print "Distance (m): %s" % str(self.distance)
        print "Beam center X (m): %s" % str(self.bcx)
        print "Beam center Y (m): %s" % str(self.bcy)
        print "Pixel Size  X (m): %s" % str(self.psx)
        print "Pixel Size  Y (m): %s" % str(self.psy)


#===================================================================================================================
if __name__ == '__main__':
    pass  #check imports
    #modules = {'fabio': False, 'h5py': False, 'pyFAI': False, 'numpy': False, 'PIL': False}

    #argv = sys.argv[1:]
    #Let's get started
    #main(IO, X, HF, True)
    #print 'called'




