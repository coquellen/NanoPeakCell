import h5py
import numpy as np
#from libtbx import easy_pickle
#try:
#    from scitbx.array_family import flex
#    CCTBX=True
#except:
#    CCTBX=False

#from NPC.NPC_CBF import write
import os
#from NPC.NPC_routines import dpack

class SaveHits(object):
    formats = []
    def __init__(self, args,energy=False):
        self.args = args
        for format in self.args['output_formats'].split():
            if self.args['TimeResolved']:
                format += '_TR'
            self.formats.append(globals()[format.upper()](self.args,energy=energy))

    def saveHit(self, data, *args):
        #fout = self.getOutputFilename(fn)
        for format in self.formats:
            format.SaveHit(data, *args)

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

    def SaveHit(self, img, fin):
        OutputFilename = os.path.join(self.args['output_directory'],
                                      'NPC_run%s' %self.args['num'].zfill(3),
                                      'CBF',
                                      '%s.cbf'%fout)
        write(OutputFilename, img.astype(np.int32))


class HDF5(object):
    def __init__(self, args, energy = False):
        self.args = args
        self.NframesPerH5 = 100
        self.N = 0
        self.size0, self.size1 = args['shape']
        self.energy = energy


        #Carefull - the filename_root is only there with SSX
        FileName = os.path.join(self.args['output_directory'],
                                'NPC_run%s' %self.args['num'].zfill(3),
                                'HDF5', "%s_%i_%i.h5" % (self.args['filename_root'].strip('_'), self.args['rank'], self.N))
        self.h5 = h5py.File(FileName)
        self.dset = self.h5.create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                           chunks=(1, self.size0, self.size1))

        self.Nhits = 0
        if self.energy:
            self.Edset = self.h5.create_dataset("energy", (self.NframesPerH5,))

    def SaveHit(self,img, energy=None, *args):
        self.dset[self.Nhits % self.NframesPerH5, ::] = img
        if self.energy:
            self.Edset[self.Nhits % self.NframesPerH5] = energy

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
    def __init__(self, args, energy = False):
        self.args = args
        self.NframesPerH5 = 100
        self.size0, self.size1 = args
        self.size1 = args.detector.shape[1]
        self.energy = energy
        self.name = ['on','off']


        OnFileName = os.path.join(self.args['output_directory'],
                                       'NPC_run%s' % self.args['num'].zfill(3),
                                       'HDF5',
                                       "%s_%i_%i_on.h5" % (
                                          self.args['filename_root'].strip('_'), self.args['rank'], self.N))
        self.h5_on = h5py.File(OnFileName)
        self.dset_on = self.h5_on.create_dataset("data", (self.NframesPerH5, self.size0, self.size1),
                                                  compression='gzip',
                                                  chunks=(1, self.size0, self.size1))

        OffFileName = os.path.join(self.args['output_directory'],
                                        'NPC_run%s' % self.args['num'].zfill(3),
                                        'HDF5',
                                        "%s_%i_%i_on.h5" % (
                                            self.args['filename_root'].strip('_'), self.args['rank'], self.N))
        self.h5_off = h5py.File(OffFileName)
        self.dset_off = self.h5_off.create_dataset("data", (self.NframesPerH5, self.size0, self.size1),
                                                   compression='gzip',
                                                   chunks=(1, self.size0, self.size1))

        self.dsets = [self.dset_off, self.dset_on]
        self.h5s = [self.h5_off, self.h5_on]

        self.Nhits_on = 0
        self.Nhits_off = 0
        self.Nhits = [self.Nhits_off, self.Nhits_on]

        if self.energy is not None:
            self.Edset_on = self.h5_on.create_dataset("energy", (self.NframesPerH5,))
            self.Edset_off = self.h5_off.create_dataset("energy", (self.NframesPerH5,))
            self.Edsets = [self.Edset_off, self.Edset_on]


    def SaveHit(self, img, energy, laser_status):

        self.dsets[laser_status][self.Nhits[laser_status] % self.NframesPerH5, ::] = img
        self.Nhits[laser_status] += 1
        if self.energy: self.Edsets[laser_status] = energy

        if self.Nhits[laser_status] % self.NframesPerH5 == 0:
            self.h5s[laser_status].close()
            FileName = os.path.join(self.args['output_directory'],
                                'NPC_run%s' % self.args['num'].zfill(3),
                                'HDF5', "%s_%i_%i.h5" % (self.args['filename_root'].strip('_'), self.args['rank'],
                                                         self.Nhits[laser_status] / self.NframesPerH5))

            self.h5s[laser_status] = h5py.File(FileName)
            self.dsets[laser_status] = self.h5s[laser_status].create_dataset("data", (self.NframesPerH5, self.size0, self.size1), compression='gzip',
                                           chunks=(1, self.size0, self.size1))





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

