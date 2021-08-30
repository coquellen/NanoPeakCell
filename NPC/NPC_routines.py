import sys

class ROI(object):
    def __init__(self, options, shape):
        self.getROI(options, shape)


    def getROI(self, args, shape):
        if args['roi'].lower() == 'none':
            self.xmax, self.ymax = shape
            self.xmin, self.ymin = 0, 0
            self.active = False

        else:
            y1, x1, y2, x2 = args['roi'].split()
            self.xmax = max(int(x1), int(x2))
            self.xmin = min(int(x1), int(x2))
            self.ymax = max(int(y1), int(y2))
            self.ymin = min(int(y1), int(y2))
            self.active = True
        self.tuple = self.xmin, self.xmax, self.ymin, self.ymax

def IsHit(img, threshold, npixels):
    return img[img > float(threshold)].size >= npixels

def InitDetector(args):
    import pyFAI
    detector = None
    if args['experiment'] == 'LCLS':
        from NPC.Detectors import CSPAD
        return CSPAD()
    elif args['experiment'] == 'SACLA':
        from NPC.Detectors import MPCCD
        return MPCCD()
    else:
        try:
            detector_name = args['detector']
            if detector_name == 'Eiger16M_ID23EH1':
                from NPC.Detectors import  Eiger16M
                return Eiger16M()
            else:
                detector = pyFAI.detectors.detector_factory(detector_name)
                detector.overload = GetOverload(detector_name)
                return detector

        # TODO: not the correct exception - needs to be rewritten
        except RuntimeError:
            print("This detector is not implemented in pyFAI / NPC - Please contact us")
            sys.exit(1)

OVL = {'pilatus': 1048500, 'eiger':1048500}

def GetOverload(det):
    for key, value in OVL.iteritems():
        if key in det:
            return value
    return None


class Correction(object):

    def __init__(self, args, detector, roi):
        self.args = args
        self.detector = detector
        self.roi = roi
        self.Mask()
        self.AI = AI(args,detector, self.mask)
        self.DarkMapping = {0: self.NoCorrection, 1: self.CorrectDark, 2:self.SubtractBKG, 3:self.CorrectNSubtract}# 2: self.correctmask, 3: self.correctboth}
        self.DarkCorrection = self.DarkMapping[self.Dark()]


    def Dark(self):
        if self.args['dark'].lower() == 'none':
            if self.AI is None:
                return 0
            else:
                return 2
        else:
            if not self.openDark():
                self.args['dark'].lower() == 'none'
                self.Dark()
            if self.AI is None:
                return 1
            else:
                return 3

    def Mask(self):
        if self.args['mask'].lower() == 'none':
            #This allows to have stripes of Pilatus/Eiger detector masked out automatically
            self.mask = -1 * (self.detector.mask - 1)
            return
        else:
            self.openMask()
            if not self.openMask():
                self.args['mask'].lower() == 'none'
                self.Mask()
            return

    def openDark(self):
        import h5py
        try:
            darkFN, path = self.args['dark'].split(':')
        except:
            darkFN = self.args['dark']
            path = 'data'

        h51 = h5py.File(darkFN, 'r')
        self.dark = h51[path][:]
        h51.close()
        if self.dark.shape != self.detector.shape:
            return False
        else: return True

    def openMask(self):
        import h5py
        try:
            maskFN, path = self.args['mask'].split(':')
        except:
            maskFN = self.args['mask']
            path = 'data'
        h51 = h5py.File(maskFN, 'r')
        self.mask = -1 * (h51[path][:] - 1)
        h51.close()
        if self.mask.shape != self.detector.shape:
            return False
        else:
            return True


    def NoCorrection(self, img):
        return img

    def CorrectDark(self, img, roi=False):
        if roi:
            return img[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax] - self.dark[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax]
        else:
            return  img -self.dark


    def CorrectMask(self, img, roi=False):
        if roi:
            return img[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax] * self.mask[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax]
        else:
            return img * self.mask

    def SubtractBKG(self, img):
        if img.shape != self.AI.resolution:
            return img
        else:
            return self.AI.SubtractBkgAI(img)

    def CorrectNSubtract(self, img):
        if img.shape != self.AI.resolution:
            print("Azimuthal Integration is impossible")
            return img
        else:
            return self.AI.SubtractBkgAI(img -self.args.dark)


class AI(object):
    """ This class instantitiates an azimutal integrator object
        from pyFAI, which will be further used to perform
	    background subtraction.
    """

    def __init__(self, args, detector, mask):
        import pyFAI

        self.detector = detector
        self.mask = mask
        self.psx = self.detector.pixel1
        self.psy = self.detector.pixel2
        self.resolution = self.detector.shape

        self.distance = args['detector_distance'] / 1000.  # Convert from meter (NPC) to mm (pyFAI)
        self.bcx = args['beam_x'] * self.psx
        self.bcy = args['beam_y'] * self.psy
        self.wl = args['wavelength']

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

    def SubtractBkgAI(self, img):
        return self.ai.separate(img.astype("float64"), npt_rad=1024, npt_azim=512, unit="2th_deg",
                                                percentile=50, mask=self.mask,
                                                restore_mask=True)[0]

    def test(self):
        print("Distance (m): %s" % str(self.distance))
        print("Beam center X (m): %s" % str(self.bcx))
        print("Beam center Y (m): %s" % str(self.bcy))
        print("Pixel Size  X (m): %s" % str(self.psx))
        print("Pixel Size  Y (m): %s" % str(self.psy))

try:
    from scitbx.array_family import flex
    CCTBX = True
except ImportError:
    CCTBX = False


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

#TODO : Add peak finding here
