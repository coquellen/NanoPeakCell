import pyFAI

class AI(object):
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
