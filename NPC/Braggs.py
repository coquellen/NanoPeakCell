import numpy as np
from scipy import ndimage
from scipy.spatial import KDTree as cKDTree

def apply_mask():
        self.data[:] = self.data * np.logical_not(self.detector.mask[self.xmin:self.xmax,self.ymin:self.ymax]) - self.dark[self.xmin:self.xmax,self.ymin:self.ymax]

def remove_beam_center(self):
        self.data[self.options['beam_y'] - self.extend:self.options['beam_y'] + self.extend,
                  self.options['beam_x'] - self.extend:self.options['beam_x'] + self.extend] = 0

def find_peaks(data, threshold):
        return local_maxima(data.astype(np.int32), 3, 3, threshold)

def validate_tuple(self, value, ndim):
        if not hasattr(value, '__iter__'):
            return (value,) * ndim
        if len(value) == ndim:
            return tuple(value)
        raise ValueError("List length should have same length as image dimensions.")

def binary_mask(radius, ndim):
        "Elliptical mask in a rectangular array"
        radius = validate_tuple(radius, ndim)
        points = [np.arange(-rad, rad + 1) for rad in radius]
        if len(radius) > 1:
            coords = np.array(np.meshgrid(*points, indexing="ij"))
        else:
            coords = np.array([points[0]])
        r = [(coord/rad)**2 for (coord,rad) in zip(coords,radius)]
        return sum(r) <= 1

def local_maxima(image, radius, separation, threshold):
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


        #x, y = maxima[:,0], maxima[:,1]
        #max_val  = image[x,y].reshape(1,len(maxima))
        #peaks = np.concatenate((maxima,max_val), axis = 1)

        return maxima[:,0], maxima[:,1], image[maxima[:,0],maxima[:,1]].reshape(1,len(maxima))



    
