import numpy as np
from pyFAI.detectors import Detector


class MPCCD(Detector):
    def __init__(self):
        Detector.__init__(self)
        self.resolution=(2399,2399)
        self.shape = self.resolution
        self.pixel1 = 5e-5
        self.pixel2 = 5e-5
        self.mask = np.zeros(self.shape)
        self.spline = None


class CSPAD(Detector):
    def __init__(self):
        Detector.__init__(self)
        self.resolution=(1800,18000)
        self.shape = self.resolution
        self.pixel1 = 11e-5
        self.pixel2 = 11e-5
        self.mask = np.zeros(self.shape)
        self.spline = None