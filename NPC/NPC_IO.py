import h5py
import numpy as np
from libtbx import easy_pickle
try:
    from scitbx.array_family import flex
    CCTBX=True
except:
    CCTBX=False

from NPC.NPC_CBF import write
import os
from NPC.NPC_routines import dpack

class SaveHits(object):
    formats = []
    def __init__(self, args):
        self.args = args
        for format in self.args['output_formats'].split():
            #if self.args[TimeResolved:
            #    format += '_TR'
            self.formats.append(globals()[format.upper()](self.args))

    def saveHit(self,img, fn):
        fout = self.getOutputFilename(fn)
        for format in self.formats:
            format.SaveHit(img, fout)

    def getOutputFilename(self, fn):
        return os.path.basename(os.path.splitext(fn)[0])

    def ClosingOpenH5(self):
        for format in self.formats:
            try:
                format.CloseH5()
            except: continue


class CBF(object):
    def __init__(self, args):
        self.args = args

    def SaveHit(self,img,fout):
        OutputFilename = os.path.join(self.args['output_directory'],
                                      'NPC_run%s' %self.args['num'].zfill(3),
                                      'CBF',
                                      '%s.cbf'%fout)
        write(OutputFilename, img.astype(np.int32))


class HDF5(object):
    def __init__(self, args):
        self.args = args
        self.NframesPerH5 = 100
        self.size0, self.size1 = args['shape']

        #Carefull - the filename_root is only there with SSX
        FileName = os.path.join(self.args['output_directory'],
                                'NPC_run%s' %self.args['num'].zfill(3),
                                'HDF5', "%s_%i_0.h5" % (self.args['filename_root'].strip('_'), self.args['rank']))
        self.h5 = h5py.File(FileName)
        self.dset = self.h5.create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                           chunks=(1, self.size0, self.size1))

        self.Nhits = 0
        #if self.args.experiment == 'LCLS':
        #    self.Edset = self.h5.create_dataset("energy", (self.NframesPerH5,))

    def SaveHit(self,img, fout):
        self.dset[self.Nhits % self.NframesPerH5, ::] = img
        #if self.args.experiment == 'LCLS':
        #   self.Edset[self.Nhits % self.NframesPerH5] = energy
        self.Nhits += 1
        if self.Nhits % self.NframesPerH5 == 0:
            self.h5.close()
            FileName = os.path.join(self.args['output_directory'],
                                    'NPC_run%s' % self.args['num'].zfill(3),
                                    'HDF5', "%s_%i_%i.h5" % (self.args['filename_root'].strip('_'), self.args['rank'], self.Nhits / self.NframesPerH5))

            self.h5 = h5py.File(FileName)
            self.dset = self.h5.create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                               chunks=(1, self.size0, self.size1))


    def CloseH5(self):
        shape = (self.Nhits % self.NframesPerH5, self.size0, self.size1)
        self.dset.resize(shape)
        #if self.args.experiment == 'LCLS':
        #  self.Edset.resize(self.Nhits % self.NframesPerH5)
        self.h5.close()


class HDF5_TR(object):
    def __init__(self, args):
        self.args = args
        self.NframesPerH5 = 100
        self.size0 = args.detector.shape[0]
        self.size1 = args.detector.shape[1]
        self.args.H5Dir = 'HDF5'

        self.Nhits_on = 0
        self.Nhits_off = 0
        self.Nhits = [self.Nhits_off, self.Nhits_on]

        OnFileName = os.path.join(self.args.procdir, self.args.H5Dir,
                                      "%s_%i_0_on.h5" % (self.args.output_root, self.args.rank))
        self.h5_on = h5py.File(OnFileName)
        self.dset_on = self.h5_on.create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                                     chunks=(1, self.size0, self.size1))
        OffFileName = os.path.join(self.args.procdir, self.args.H5Dir,
                                      "%s_%i_0_off.h5" % (self.args.output_root, self.args.rank))
        self.h5_off = h5py.File(OffFileName)
        self.dset_off = self.h5_off.create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                                       chunks=(1, self.size0, self.size1))
        self.dsets = [self.dset_off, self.dset_on]
        self.h5s = [self.h5_off, self.h5_on]



class PICKLES(object):
    def __init__(self, args):
        self.args = args
        self.args.overload=65535

    def SaveHit(self,img, fn):
        if CCTBX:
            pixels = flex.int(img.astype(np.int32))
            data = dpack(data=pixels,
                         distance=self.args.distance,
                         pixel_size=self.args.detector.pixel1,
                         wavelength=self.args.wl,
                         beam_center_x=self.args.beamy * self.args.detector.pixel1,
                         beam_center_y=self.args.beamx * self.args.detector.pixel1,
                         ccd_image_saturation=self.args.overload,
                         saturated_value=self.args.detector.overload)
            OutputFileName = os.path.join(self.args.procdir, "PICKLES","%s.pickles"%fn)
            easy_pickle.dump(OutputFileName, data)

