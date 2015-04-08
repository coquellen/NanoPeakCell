import NPC.utils as utils
import imp
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

comm = MPI.COMM_WORLD
rank = comm.rank
size = comm.size


class main(object):
    def __init__(self, options):
        self.options = options

        if rank == 0:
            utils.startup(options)
            self.images = utils.get_images(options['filename_root'],
                                           options['file_extension'],
                                           options['data'],
                                           options['randomizer'])

            for i in range(1, size): comm.send(self.images, dest=i)

        if rank != 0: self.images = comm.recv(source=0)

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
        self.total = len(self.images)
        self.chunk = max(int(round(float(self.total) / 1000.)), 10)
        self.hit = 0
        self.out = 0
        self.signal = True
        #myframes = [self.images[i] for i in xrange(self.total) if (i + rank) % size == 0]

        max_proj = np.zeros(self.detector.shape, np.int32)
        avg = np.zeros_like(max_proj)
        #for fname in myframes:
        for idx in xrange(rank,self.total,size):
            fname = self.images[idx]
            hit, imgmax, imgmin, imgmed, peaks,working = self.HitFinder.get_hit(fname)
            if hit == 1:
                #print '%s with proc %i' % (fname, rank)
                self.hit += 1
                avg += working
                maxids = np.where(working > max_proj)
                max_proj[maxids] = working[maxids]


        t2 = time.time()
        t_final = comm.reduce(t2-t1, op=MPI.SUM,root = 0)
        hit_final = comm.reduce(self.hit, op=MPI.SUM,root = 0)

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
            avg_final = avg / hit_final
            cleanmax = max_proj_final - avg


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
	
	
    

