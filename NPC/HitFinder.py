import os
import fabio
import h5py
import numpy as np
from scipy import ndimage
from scipy.spatial import KDTree as cKDTree



class HitFinder(object):

    def __init__(self, options, Detector, AI):
        self.options = options
        self.detector = Detector
        if options['mask'].lower() != 'none':
            self.detector.mask = self.open(options['mask'])
        self.ai = AI
        if options['dark'].lower() != 'none':
            self.dark = self.open(options['dark'])
        else: self.dark = np.zeros(self.detector.shape, dtype='uint16')
        self.peaks = []
        self.hit = 0
        self.set_output_filename_mapping = {'SSX': self.set_ssx, 'SFX_SACLA': self.set_sacla,'SFX_LCLS': self.set_lcls}
        self.threshold = self.options['threshold']
        self.npixels = self.options['npixels']
        self.extend = 15
        self.type = np.float32

        if self.options['ROI'] == 'None':
            dim1 = self.detector.shape[0]
            dim2 = self.detector.shape[1]
            self.data = np.empty((dim1, dim2))
            self.xmax = dim1
            self.xmin = 0
            self.ymin = 0
            self.ymax = dim2

        else:
            self.xmin, self.xmax, self.ymin, self.ymax = self.options['ROI_tuple']
            dim1 = self.xmax - self.xmin
            dim2 = self.ymax - self.ymin
            self.data = np.empty((dim1, dim2))
            #print self.data.shape



    def open(self,filename):
        if filename.endswith('h5'):
                h5 = h5py.File(filename)
                data = h5['data'][:]
                h5.close()
                return data
        else:
                return fabio.open(filename).data

    def get_hit(self,name):
        self.apply_mask()
        self.bkg_sub()
        if self.is_hit():
            self.set_output_filename_mapping[self.options['experiment']](name)
            self.hit = 1
            if self.options['bragg_search']:
                self.peaks = self.find_peaks()
            #self.save_hit()
        else: self.hit = 0
        return self.hit, np.max(self.data), np.min(self.data), np.median(self.data), len(self.peaks)#, self.data

    def apply_mask(self):
        self.data[:] = self.data * np.logical_not(self.detector.mask[self.xmin:self.xmax,self.ymin:self.ymax]) - self.dark[self.xmin:self.xmax,self.ymin:self.ymax]

    def set_ssx(self, fname):
        if 'eiger' in self.options['detector'].lower() and 'h5' in self.options['file_extension']:
            self.filename, group, index, ovl, self.type = fname
            fileout = self.filename.split('.h5')[0]
            fileout = os.path.basename(fileout)
            self.root = "%s_%s"%(fileout, str(index).zfill(6))

        else:
            self.root = os.path.basename(fname)
            self.root, self.extension = os.path.splitext(self.root)

    def set_sacla(self, name):
        run,tag = name
        self.root ='%s_tag_%s' %(run,tag)

    def set_lcls(self,id):
        id0, id1 = id
        self.root = '%s_%s_%i_%i'%(self.options['experiment'],self.options['runnumber'],id0,id1)

    def bkg_sub(self):
        if self.options['background_subtraction'].lower() !=  'none':
            if self.data.shape == self.detector.shape:
                #BkgCorr with pyFAI Azimuthal Integrator
                self.data = self.ai.ai.separate(self.data.astype("float64"), npt_rad=1024, npt_azim=512, unit="2th_deg", percentile=50, mask=self.detector.mask,
                                     restore_mask=True)[0]
            else: print 'Error with file'

    def remove_beam_center(self):
        #Remove beam stop area (i.e = 0)
        self.data[self.options['beam_y'] - self.extend:self.options['beam_y'] + self.extend,
                  self.options['beam_x'] - self.extend:self.options['beam_x'] + self.extend] = 0


    def is_hit(self):

        return self.data[self.data >= self.threshold].size >= self.npixels

    def find_peaks(self):
        peaks = self.local_maxima(self.data.astype(np.int32), 3, 3, self.options['bragg_threshold'])
        return peaks

    def validate_tuple(self, value, ndim):
        if not hasattr(value, '__iter__'):
            return (value,) * ndim
        if len(value) == ndim:
            return tuple(value)
        raise ValueError("List length should have same length as image dimensions.")

    def binary_mask(self,radius, ndim):
        "Elliptical mask in a rectangular array"
        radius = self.validate_tuple(radius, ndim)
        points = [np.arange(-rad, rad + 1) for rad in radius]
        if len(radius) > 1:
            coords = np.array(np.meshgrid(*points, indexing="ij"))
        else:
            coords = np.array([points[0]])
        r = [(coord/rad)**2 for (coord,rad) in zip(coords,radius)]
        return sum(r) <= 1

    def local_maxima(self, image, radius, separation, threshold):
        ndim = image.ndim
        threshold -= 1
        # The intersection of the image with its dilation gives local maxima.
        if not np.issubdtype(image.dtype, np.integer):
            raise TypeError("Perform dilation on exact (i.e., integer) data.")
        #footprint = self.binary_mask(radius, ndim)
        s = ndimage.generate_binary_structure(ndim, 2)
        # scale it up to the desired size
        footprint = ndimage.iterate_structure(s, int(radius))

        dilation = ndimage.grey_dilation(image, footprint=footprint, mode='constant')

        maxima = np.vstack(np.where((image == dilation) & (image > threshold))).T[:,::-1]
        if not np.size(maxima) > 0:
            #warnings.warn("Image contains no local maxima.", UserWarning)
            return np.empty((0, ndim))

        # Flat peaks return multiple nearby maxima. Eliminate duplicates.
        if len(maxima) > 0:
            while True:
                duplicates = cKDTree(maxima, 30).query_pairs(separation)
                if len(duplicates) == 0:
                    break
                to_drop = []
                for pair in duplicates:
                    # Take the average position.
                    # This is just a starting point, so we won't go into subpx precision here.
                    merged = maxima[pair[0]]
                    merged = maxima[[pair[0], pair[1]]].mean(0).astype(int)
                    maxima[pair[0]] = merged  # overwrite one
                    to_drop.append(pair[1])  # queue other to be dropped

                maxima = np.delete(maxima, to_drop, 0)

        # Do not accept peaks near the edges.
        shape = np.array(image.shape)
        margin = int(separation) // 2
        near_edge = np.any((maxima < margin) | (maxima > (shape - margin)), 1)
        maxima = maxima[~near_edge]
        #if not np.size(maxima) > 0:
            #warnings.warn("All local maxima were in the margins.", UserWarning)


        x, y = maxima[:,0], maxima[:,1]
        max_val  = image[x,y].reshape(len(maxima),1)
        peaks = np.concatenate((maxima,max_val), axis = 1)

        return peaks

    def save_hit(self):

            self.result_folder = self.options['output_directory']
            self.num = self.options['num']
            #if self.options['ROI'].lower() is not 'none':


            # Conversion to edf
            if 'edf' in self.options['output_formats']:
                OutputFileName = os.path.join(self.result_folder, 'EDF_%s'%self.num.zfill(3), "%s.edf" % self.root)
                edfout = fabio.edfimage.edfimage(data=self.data.astype(np.float32))
                edfout.write(OutputFileName)

            if 'cbf' in self.options['output_formats']:
                OutputFileName = os.path.join(self.result_folder, 'CBF_%s'%self.num.zfill(3), "%s.cbf" % self.root)
                cbfout = fabio.cbfimage.cbfimage(data=self.data.astype(np.float32))
                cbfout.write(OutputFileName)

            # Conversion to H5
            if 'hdf5' in self.options['output_formats']:

                OutputFileName = os.path.join(self.result_folder, 'HDF5_%s'%self.num.zfill(3), "%s.h5" % self.root)
                OutputFile = h5py.File(OutputFileName, 'w')
                OutputFile.create_dataset("data", data=self.data, compression="gzip", dtype=self.type)
                if self.options['bragg_search']:
                    OutputFile.create_dataset("processing/hitfinder/peakinfo", data=self.peaks.astype(np.int))
                OutputFile.close()

            # Conversion to Pickle
            if cctbx and 'pickles' in self.options['output_formats']:
                    pixels = flex.int(self.data.astype(np.int32))
                    pixel_size = self.detector.pixel1
                    data = dpack(data=pixels,
                             distance=self.options['distance'],
                             pixel_size=pixel_size,
                             wavelength=self.options['wavelength'],
                             beam_center_x=self.options['beam_y'] * pixel_size,
                             beam_center_y=self.options['beam_x'] * pixel_size,
                             ccd_image_saturation=self.detector.overload,
                             saturated_value=self.detector.overload)
                    data = crop_image_pickle(data)
                    OutputFileName = os.path.join(self.result_folder, 'PICKLES_%s'%self.num.zfill(3), "%s.pickle" % self.root)
                    easy_pickle.dump(OutputFileName, data)

if __name__ == '__main__':
    from test import options_SSX
    from utils import get_filenames
    test = HitFinder(options_SSX,None,None)
    images = get_filenames(options)
    test.data = fabio.open(images[100])

    
