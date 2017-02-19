import NPC.utils as utils
import sys
import time
import multiprocessing
import pyFAI
import pyFAI.detectors
import numpy as np
import Queue

PUBSUB = False

# Try to genuinely import pubsub #
import wx
version = wx.__version__

try:
    if version[0] == '3' or (version[0] == '2' and int(version[1]) >= 9):
        from wx.lib.pubsub import pub
        PUBSUB = True
    elif version[0] == '2' and version[1] == '8' and int(version[2]) >= 11:
        from wx.lib.pubsub import setupkwargs
        from wx.lib.pubsub import pub
        PUBSUB = True
except ImportError: 
    try:
        from pubsub import pub
        PUBSUB = True
    except ImportError:
        print """Pubsub not imported and therefore disabled.
                 NPC uses the pubsub v3 API. It seems that your version of wxpython is outdated (<2.8.11)
                 Please install a newer version of wxpython and restart NPC
                 If this does not solve the problem, please contact us, with your latest configuration"""



class DataProcessing(object):

    def __init__(self, options):
        self.options = options

        self.images = utils.get_images(options['filename_root'],
                                       options['file_extension'],
                                       options['data'],
                                       options['randomizer'])

        detector_name = options['detector']
        self.detector = pyFAI.detectors.Detector.factory(detector_name)
        self.ai = AI(self.options, self.detector)

        utils.startup(self.options)

        self.run()

    def run(self):

        self.start_mp()
        #Deal with dark
        #self.calculate_mask()
        self.find_hits()


    def start_mp(self):
        """ Start as many processes as set by the user
	    """
        from MultiProcess import MProcess_SSX as MProcess

        self.tasks = multiprocessing.JoinableQueue(maxsize=1000)
        self.results = multiprocessing.Queue()

        self.consumers = [
            MProcess(self.tasks, self.results, self.options, self.detector,
                     self.ai) for i in xrange(self.options['cpus'])]
        for w in self.consumers:
            w.start()


    #----------------------------------------------
    def find_hits(self):
        self.t1 = time.time()
        self.total = len(self.images)
        self.chunk = max(int(round(float(self.total) / 1000.)), 10)
        print '\n= Job progression = Hit rate =    Max   =   Min   = Median = #Peaks '
        self.hit = 0
        self.peaks_all_frame = []
        self.hitnames = []
        index = 0
        self.out = 0
        self.signal = True

        max_proj = np.zeros(self.detector.shape, np.float32)
        avg = np.zeros_like(max_proj)
        cleanmax = np.zeros_like(max_proj)

        if 'eiger' in self.detector: self.load_eiger_task_queue(self)
        else: self.load_task_queue(self)

        self.get_results()
        self.get_final_stats()


    def load_task_queue(self):


        for fname in self.images:
            if self.signal:

                self.tasks.put(fname, block=True, timeout=None)

                self.get_results()
            else:
                break

        for i in xrange(self.options['cpus']):
            self.tasks.put(None)

    def get_result(self):
                while True:
                    try:
                        hit, imgmax, imgmin, imgmed, peaks,working = self.results.get(block=True, timeout=0.01)
                        self.hit += hit
                        self.out += 1
                        percent = (float(self.out) / (self.total)) * 100.
                        hitrate = (float(self.hit) / float(self.out)) * 100.
                        if hit == 1:
                            self.hitnames.append(fname)
                            avg += working
                            maxids = np.where(working > max_proj)
                            max_proj[maxids] = working[maxids]
                        if self.out % self.chunk == 0:
                            print '     %6.2f %%       %5.1f %%    %8.2f    %7.2f  %6.2f %4d  (%i out of %i images) \r' % (
                                percent, hitrate, imgmax, imgmin, imgmed,
                                peaks, self.out, self.total),  #while True:
                            sys.stdout.flush()
                    except Queue.Empty:
                        break





            if self.out == self.total:
                print '     %6.2f %%       %5.1f %%    %8.2f    %7.2f  %6.2f %4d  (%i out of %i images) \r' % (
                    percent, hitrate, imgmax, imgmin, imgmed, peaks, self.out, self.total),
                break

        print '\nOverall, found %s hits in %s files --> %5.1f %% hit rate with a threshold of %s' % (
            self.hit, self.total, ((float(self.hit) / (self.total)) * 100.), self.options['threshold'])
        if PUBSUB: pub.sendMessage('Done')
        self.t2 = time.time()
        print "\nIt took %4.2f seconds to process %i images (i.e %4.2f images per second)" % (
            (self.t2 - self.t1), len(self.images), float(len(self.images) / (self.t2 - self.t1)))

        avg = avg / self.hit
        cleanmax = max_proj - avg




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


#To go from 2048 spline to 1024
#import pyFAI.spline
#s=pyFAI.spline.Spline()
#s.read("distorsion.spline")
#s.bin(2)
#s.write("distorsion_1024.spline")







        #----------------------------------------------









#===================================================================================================================
if __name__ == '__main__':
    pass
	
    

