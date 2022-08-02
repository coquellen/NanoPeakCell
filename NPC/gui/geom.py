import numpy as np
from scipy.ndimage.interpolation import rotate
import os

tile2det= {(4112, 1030): (6000, 6000),  # Jungfrau 4M
           (1480, 1552): (1800, 1800),  # CSPAD
           (5632,  384): (1800, 1800)}

class Tile(object):

    def __init__(self, name):
        self.name = name

        self.xmin = 0
        self.xmax = 0
        self.ymin = 0
        self.ymax = 0

        self.min_ss = 0
        self.max_ss = 0
        self.min_fs = 0
        self.max_fs = 0

        self.fs = 'x'
        self.ss = 'y'

        self.cornerx = 0
        self.cornery = 0


    def setup(self, size):

        self.size = tile2det[size]

        x = float(self.fs.split('x')[0])
        y = float(self.fs.split('y')[0].split('x')[1])
        self.alpha_r = np.arctan2(y, x)
        self.alpha = np.degrees(self.alpha_r) #* 180 / np.pi

        data_tile = np.zeros((int(self.max_ss) - int(self.min_ss) + 1,
                              int(self.max_fs) - int(self.min_fs) + 1))  # [::-1,:]  # , indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]

        delta_x = float(self.cornerx)
        delta_y = float(self.cornery)

        rot = rotate(data_tile, self.alpha)

        if int(self.alpha) in range(80, 100):
            self.xmin = int(round((self.size[0] / 2) - delta_y - rot.shape[0]))
            self.xmax = int(round((self.size[0] / 2) - delta_y))
            self.ymin = int(round((self.size[1] / 2) + delta_x - rot.shape[1]))
            self.ymax = int(round((self.size[1] / 2) + delta_x))

        elif int(self.alpha) in range(175, 185) or int(self.alpha) in range(-185, -175):
            self.xmin = int(round((self.size[0] / 2) - delta_y))
            self.xmax = int(round((self.size[0] / 2) - delta_y + rot.shape[0]))
            self.ymin = int(round((self.size[1] / 2) + delta_x - rot.shape[1]))
            self.ymax = int(round((self.size[1] / 2) + delta_x))

        elif int(self.alpha) in range(-95, -85) or int(self.alpha) in range(265, 275):
            self.xmin = int(round((self.size[0] / 2) - delta_y))
            self.xmax = int(round((self.size[0] / 2) - delta_y + rot.shape[0]))
            self.ymin = int(round((self.size[1] / 2) + delta_x))
            self.ymax = int(round((self.size[1] / 2) + delta_x + rot.shape[1]))

        else:
            self.xmin = int(round((self.size[0] / 2) - delta_y - rot.shape[0]))
            self.xmax = int(round((self.size[0] / 2) - delta_y))
            self.ymin = int(round((self.size[1] / 2) + delta_x))
            self.ymax = int(round((self.size[1] / 2) + delta_x + rot.shape[1]))

        del rot

        self.c, self.s = np.cos(self.alpha_r), np.sin(self.alpha_r)
        #self.R = np.array(((c, -s), (s, c)))
        #del c, s

    def rotate_peaks(self, data):
        #data = np.array(data) + self.size[0] / 2.
        x = data[:,0]
        y = data[:,1]

        xx = x * self.c + y * self.s
        yy = -x * self.s + y * self.c

        return xx,yy
            # Needs corner_x, corner_y
        # Needs alpha,
        # Needs rotate_tile
        # Needs rotate points


class Geom(object):

    param_attr = {'min_fs': ('min_fs', float),
                  'max_fs': ('max_fs', float),
                  'min_ss': ('min_ss', float),
                  'max_ss': ('max_ss', float),
                  '/fs =':  ('fs', str),
                  '/ss =':  ('ss', str),
                  'corner_x': ('cornerx', float),
                  'corner_y': ('cornery', float)
                  }

    def __init__(self):
        self.tiles = []

    def load(self, geom_fn, open_fn):
        self.tiles = []
        self.size = self.parse_geom_file(geom_fn, open_fn)
        self.det_size = tile2det[self.size]
        self.reconstructed = np.zeros(self.det_size)
        for tile in self.tiles:
            tile.setup(self.size)

    def grep(self, sequence, buffer):
        return [line for line in sequence if buffer in line and not line.startswith('bad')]

    def retrieve_geom_params(self, lines, tile):
        all = self.grep(lines, tile.name)
        for param in self.param_attr.keys():
            attr, typ = self.param_attr[param]
            value = grep(all, param)[0].split('=')[1].strip()
            setattr(tile, attr, typ(value))

    def parse_geom_file(self, filename, openfn=True):
        self.max_fs = 0
        self.max_ss = 0
        if openfn:
          lines = open(filename).readlines()
        else:
          lines = filename.split('\n')
        tiles_name = [line.split('/')[0] for line in lines if 'max_fs' in line and 'bad_' not in line]
        for tile_name in tiles_name:
            tile = Tile(tile_name)
            self.tiles.append(tile)
            self.retrieve_geom_params(lines, tile)
            self.max_fs = max(self.max_fs, int(float(tile.max_fs))+1)
            self.max_ss = max(self.max_ss, int(float(tile.max_ss))+1)

        return self.max_ss, self.max_fs

    def reconstruct(self, data):

        for tile in self.tiles:
            self.reconstructed[tile.xmin:tile.xmax, tile.ymin:tile.ymax] = rotate(data[int(tile.min_ss):int(tile.max_ss) + 1, int(tile.min_fs):int(tile.max_fs) + 1][::-1 ,:], tile.alpha)

        # The origin of CsPAD detector is lower right corner; therefore we need the transpose of this reconstruction
        if self.size == (1480, 1552):
            return self.reconstructed[:, ::-1]
        else:
            return self.reconstructed


def grep(sequence, buffer):
    return [line for line in sequence if buffer in line and not line.startswith('bad')]


def retrieve_geom_params(lines, tile):
    results = []
    all = grep(lines, tile)
    for param in ['min_fs', 'max_fs', 'min_ss', 'max_ss', '/fs =', '/ss =', 'corner_x', 'corner_y']:
        l = grep(all, param)
        results.append(l[0].split('=')[1].strip())
    return results


def retrieve_geom_params_euxfel(lines, tile):
    results = []
    all = grep(lines, tile)
    for param in ['min_fs', 'max_fs', 'min_ss', 'max_ss', '/fs =', '/ss =', 'corner_x', 'corner_y', 'dim1']:
        l = grep(all, param)
        results.append(l[0].split('=')[1].strip())
    return results


def parse_geom_file(filename, openfn=True):
    geom_params = {}
    max_fs = 0
    max_ss = 0
    if openfn:
        lines = open(filename).readlines()
    else:
        lines = filename.split('\n')
    tiles = [line.split('/')[0] for line in lines if 'max_fs' in line and 'bad_' not in line]
    for tile in tiles:
        params = retrieve_geom_params(lines, tile)
        max_fs = max(max_fs, int(float(params[1])) + 1)
        max_ss = max(max_ss, int(float(params[3])) + 1)
        geom_params[tile] = params

    return geom_params, (max_ss, max_fs)

def parse_geom_file_euxfel(filename, openfn=True):
    geom_params = {}
    max_fs = 0
    max_ss = 0
    dim1 = 16
    if openfn:
        lines = open(filename).readlines()
    else:
        lines = filename.split('\n')
    tiles = [line.split('/')[0] for line in lines if 'max_fs' in line and 'bad_' not in line]
    for tile in tiles:
        params = retrieve_geom_params_euxfel(lines, tile)
        max_fs = max(max_fs, int(float(params[1])) + 1)
        max_ss = max(max_ss, int(float(params[3])) + 1)
        geom_params[tile] = params

    return geom_params, (dim1, max_ss, max_fs)


def parse_geom_file_quadrants(filename, openfn=True):
    geom_params, (max_ss, max_fs) = parse_geom_file(filename, openfn=True)

    lines = open(filename).readlines()
    quadrants = grep(lines, 'rigid_group_collection_quadrants =')[0].split('=')[1].strip().split(',')

    QUAD = {}
    for quad in quadrants:
        QUAD[quad] = grep(lines,'rigid_group_'+quad)[0].split('=')[1].strip().split(',')


        #print quad, QUAD[quad], grep(QUAD[quad],'min_ss')

    return geom_params, (max_ss, max_fs), QUAD

def getGeomTransformations(geom_params):
    #reconstructed = np.zeros((size, size))
    size = 1800
    reconstructed = {}
    min_fs, max_fs, min_ss, max_ss = [int(p) for p in geom_params[geom_params.keys()[0]][0:4]]
    data = np.empty((max_ss - min_ss + 1, max_fs - min_fs + 1))

    for key, params in geom_params.items():

        #min_fs, max_fs, min_ss, max_ss = [int(p) for p in params[0:4]]
        #print max_fs - min_fs + 1
        #print max_ss - min_ss + 1
        x = float(params[4].split('x')[0])
        y = float(params[4].split('y')[0].split('x')[1])
        #data_tile = data[ min_ss:max_ss + 1, min_fs:max_fs + 1][::-1,:]  # , indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
        delta_x = float(params[-2])
        delta_y = float(params[-1])
        if x > 0 and y > 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x > 0 and y < 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x < 0 and y > 0:
            if np.abs(x) > 0.5:
                alpha = 180 - np.arctan(y / x) * 180. / np.pi
            else:
                alpha = 180 + np.arctan(y / x) * 180. / np.pi
        if x < 0 and y < 0:
            alpha = 180 - np.arctan(y / np.abs(x)) * 180. / np.pi

        rot = rotate(data, alpha)

        if int(alpha) in range(80, 100):
            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(175, 185):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(-95, -85) or int(alpha) in range(265, 275):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))

        else:

            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))

        reconstructed[key] = (alpha, xmin, xmax, ymin, ymax, delta_x, delta_y)

    return reconstructed


def DoReconstruct(data, geom_params, size):
    reconstructed = np.zeros((size, size))

    for params in geom_params.values():

        min_fs, max_fs, min_ss, max_ss = [int(float(p)) for p in params[0:4]]

        x = float(params[4].split('x')[0])
        y = float(params[4].split('y')[0].split('x')[1])
        data_tile = data[ min_ss:max_ss + 1, min_fs:max_fs + 1][::-1,:]  # , indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
        delta_x = float(params[-2])
        delta_y = float(params[-1])
        if x > 0 and y > 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x > 0 and y < 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x < 0 and y > 0:
            if np.abs(x) > 0.5:
                alpha = 180 - np.arctan(y / x) * 180. / np.pi
            else:
                alpha = 180 + np.arctan(y / x) * 180. / np.pi
        if x < 0 and y < 0:
            alpha = 180 - np.arctan(y / np.abs(x)) * 180. / np.pi

        rot = rotate(data_tile, alpha)

        if int(alpha) in range(80, 100):
            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(175, 185):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(-95, -85) or int(alpha) in range(265, 275):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))

        else:

            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))
        # print alpha, xmin, xmax, ymin, ymax, rot.shape
        #print
        reconstructed[xmin:xmax, ymin:ymax] = rot

    return reconstructed[:,::-1]
    #return reconstructed


def DoReconstruct_SWISSFEL(data, geom_params, size):
    reconstructed = np.zeros((size, size))

    for params in geom_params.values():

        min_fs, max_fs, min_ss, max_ss = [int(float(p)) for p in params[0:4]]

        x = float(params[4].split('x')[0])
        y = float(params[4].split('y')[0].split('x')[1])
        data_tile = data[ min_ss:max_ss + 1, min_fs:max_fs + 1]#[::-1,:]  # , indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
        delta_x = float(params[-2])
        delta_y = float(params[-1])
        if x > 0 and y > 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x > 0 and y < 0:
            alpha = np.arctan(y / x) * 180. / np.pi
        if x < 0 and y > 0:
            if np.abs(x) > 0.5:
                alpha = 180 - np.arctan(y / x) * 180. / np.pi
            else:
                alpha = 180 + np.arctan(y / x) * 180. / np.pi
        if x < 0 and y < 0:
            alpha = 180 - np.arctan(y / np.abs(x)) * 180. / np.pi

        rot = rotate(data_tile, alpha)

        if int(alpha) in range(80, 100):
            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(175, 185) or int(alpha):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(-95, -85) or int(alpha) in range(265, 275):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))

        else:

            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))
        reconstructed[xmin:xmax, ymin:ymax] = rot

    return reconstructed


def DoReconstruct_EuXFEL(data, geom_params, size):
    reconstructed = np.zeros((size, size))

    for params in geom_params.values():

        min_fs, max_fs, min_ss, max_ss = [int(float(p)) for p in params[0:4]]
        dim = int(params[-1])
        if dim <= 7:
            alpha = 90.

        if dim > 7:
            alpha = -90.
        #x = float(params[4].split('x')[0])
        #y = float(params[4].split('y')[0].split('x')[1])
        #print dim, data.shape, min_fs, max_fs, min_ss, max_ss, alpha
        data_tile = data[ dim, min_ss:max_ss + 1, min_fs:max_fs + 1]#[::-1,:]  # , indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
        delta_x = float(params[6])
        delta_y = float(params[7])
        rot = rotate(data_tile, np.deg2rad(alpha))

        if int(alpha) in range(80, 100):
            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(175, 185) or int(alpha):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x - rot.shape[1]))
            ymax = int(round((size / 2) + delta_x))

        elif int(alpha) in range(-95, -85) or int(alpha) in range(265, 275):
            xmin = int(round((size / 2) - delta_y))
            xmax = int(round((size / 2) - delta_y + rot.shape[0]))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))

        else:

            xmin = int(round((size / 2) - delta_y - rot.shape[0]))
            xmax = int(round((size / 2) - delta_y))
            ymin = int(round((size / 2) + delta_x))
            ymax = int(round((size / 2) + delta_x + rot.shape[1]))
        #print dim, xmin, xmax, ymin, ymax, data_tile.mean(), rot.mean()
        reconstructed[xmin:xmax, ymin:ymax] = rot

    return reconstructed



def DoReconstruct_dev(data, geom_params,size):
        reconstructed = np.indices((size,size))
        indices = np.indices(data.shape)#.reshape(data.shape)
        #print data.size, data.shape
        #print np.unravel_index(indices[-1,-1], indices.shape)

        #print indices[-1,-1]
        #print indices.shape


        
        for params in geom_params.values()[0:1]:

                min_fs, max_fs, min_ss, max_ss = [int(p) for p in params[0:4]]

                x = float(params[4].split('x')[0])
                y = float(params[4].split('y')[0].split('x')[1])
                data_tile = indices[:,min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]#, indices[1,::][min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
                delta_x = float(params[-2])
                delta_y = float(params[-1])
                if x > 0 and y > 0:
                    alpha = np.arctan(y/x) * 180. / np.pi
                if x > 0 and y <  0:
                    alpha =  np.arctan(y/x) * 180. / np.pi
                if x < 0 and y >  0:
                    if np.abs(x) > 0.5:alpha = 180 - np.arctan(y/x) * 180. / np.pi
                    else: alpha = 180 + np.arctan(y/x) * 180. / np.pi
                if x < 0 and  y <  0:
                    alpha = 180 - np.arctan(y/np.abs(x)) * 180. / np.pi

                rot = rotate(data[data_tile[0], data_tile[1]], alpha)


                if int(alpha) in range(80,100):
                    xmin=int(round((size / 2)-delta_y-rot.shape[0]))
                    xmax=int(round((size / 2)-delta_y))
                    ymin=int(round((size / 2)+delta_x-rot.shape[1]))
                    ymax=int(round((size / 2)+delta_x))

                elif int(alpha) in range(175,185):
                    xmin=int(round((size / 2)-delta_y))
                    xmax=int(round((size / 2)-delta_y+rot.shape[0]))
                    ymin=int(round((size / 2)+delta_x-rot.shape[1]))
                    ymax=int(round((size / 2)+delta_x))

                elif int(alpha) in range(-95,-85) or int(alpha) in range(265,275):
                    xmin=int(round((size / 2)-delta_y))
                    xmax=int(round((size / 2)-delta_y+rot.shape[0]))
                    ymin=int(round((size / 2)+delta_x))
                    ymax=int(round((size / 2)+delta_x+rot.shape[1]))

                else:

                    xmin=int(round((size / 2)-delta_y-rot.shape[0]))
                    xmax=int(round((size / 2)-delta_y))
                    ymin=int(round((size / 2)+delta_x))
                    ymax=int(round((size / 2)+delta_x+rot.shape[1]))


                #reconstructed[xmin:xmax, ymin:ymax] = rot

                #reconstructed[min_ss:max_ss + 1, min_fs:max_fs + 1] = data[data_tile[0],data_tile[1]]
        if xmax - xmin +1 != data_tile.shape[1]:
            return reconstructed[:,xmin:xmax, ymin:ymax], np.swapaxes(data_tile,1,2)
        else:
            return reconstructed[:,xmin:xmax, ymin:ymax], data_tile#print reconstructed[min_ss:max_ss + 1, min_fs:max_fs + 1]

                #print data_tile.shape, rot.shape, xmin, xmax, ymin, ymax
        #print reconstructed.max(), reconstructed.min()

        #return reconstructed



def reconstruct(data,geom):
    geom_params , shape = geom
    if data.shape == shape:
        if len(geom_params) == 64: return DoReconstruct(data,geom_params,size=1800)

        if len(geom_params) == 8:
            if data.shape == (4112, 1030):
                return DoReconstruct_SWISSFEL(data, geom_params, size=6000)
            else:
                return DoReconstruct(data, geom_params, size=2400)

        if len(geom_params) == 128: return DoReconstruct(data, geom_params, size=2000)

        if len(geom_params) == 32: return DoReconstruct_SWISSFEL(data, geom_params, size=6000)


    else:
        err = 1
        msg = 'NPC is not able to handle this type of segmented detectors.\n\
               So far NPC is able to reconstruct frames from CSPAD (LCLS) and MPCCD (SACLA) detectors.\n\
               Please contact us.'
        return data




