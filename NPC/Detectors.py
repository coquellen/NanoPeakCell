import numpy as np
#from pyFAI.detectors import Detector


class MPCCD(object):
    def __init__(self):
        self.resolution=(8*1024,512)
        self.shape = self.resolution
        self.pixel1 = 5e-5
        self.pixel2 = 5e-5
        self.mask = np.zeros(self.shape)
        self.spline = None


class CSPAD(object):
    def __init__(self):
        self.resolution=(1750,1750)
        self.shape = self.resolution
        self.pixel1 = 11e-5
        self.pixel2 = 11e-5
        self.mask = np.zeros(self.shape)
        self.spline = None

class Electron(object):
    def __init__(self):
        self.resolution=(4096,4096)
        self.shape = self.resolution
        self.pixel1 = 1.5e-5
        self.pixel2 = 1.5e-5
        self.mask = np.zeros(self.shape)
        self.spline = None


class Eiger_4M_fake(object):
    def __init__(self):
        self.resolution=(700,600)
        self.shape = self.resolution
        self.pixel1 = 7.5e-5
        self.pixel2 = 7.5e-5
        self.mask = np.zeros(self.shape)
        self.spline = None

class Frelon(object):
    def __init__(self):
        self.resolution=(1024,1024)
        self.shape = self.resolution
        self.pixel1 = 102e-6
        self.pixel2 = 102e-6
        self.mask = np.zeros(self.shape)
        self.spline = None

class Jungfrau4M(object):
    def __init__(self):
        self.resolution=(6000, 6000)
        self.shape = self.resolution
        self.pixel1 = 75e-6
        self.pixel2 = 75e-6
        self.mask = np.zeros(self.shape)
        self.spline = None

class Jungfrau16M(object):
    def __init__(self):
        self.resolution=(6000, 6000)
        self.shape = self.resolution
        self.pixel1 = 75e-6
        self.pixel2 = 75e-6
        self.mask = np.zeros(self.shape)
        self.spline = None

class Eiger500k(object):
    def __init__(self):
        self.resolution=(512, 1032)
        self.shape = self.resolution
        self.pixel1 = 75e-6
        self.pixel2 = 75e-6
        self.mask = np.zeros(self.shape)
        self.spline = None


class Pilatus1M(object):
    def __init__(self):
        self.resolution=(4362, 4148)
        self.shape = self.resolution
        self.pixel1 = 172e-6
        self.pixel2 = 172e-6
        self.mask = np.zeros(self.shape)
        self.spline = None

class Pilatus2M(object):
    def __init__(self):
        self.resolution=(1679, 1475)
        self.shape = self.resolution
        self.pixel1 = 172e-6
        self.pixel2 = 172e-6
        self.mask = np.zeros(self.shape)
        self.spline = None

class Eiger16M(object):
    def __init__(self):
        self.resolution=(4362, 4148)
        self.shape = self.resolution
        self.pixel1 = 75e-6
        self.pixel2 = 75e-6
        self.mask = np.zeros(self.shape)
        self.spline = None


class AgipD(object):
    def __init__(self):
        self.resolution = (2000, 2000)
        self.shape = self.resolution
        self.pixel1 = 2.0e-4
        self.pixel2 = 2.0e-4
        self.mask = np.zeros(self.shape)
        self.spline = None


class Epix10k2M(object):
    def __init__(self):
        self.resolution=(1800,1800)
        self.shape = self.resolution
        self.pixel1 = 1e-4
        self.pixel2 = 1e-4
        self.mask = np.zeros(self.shape)
        self.spline = None
