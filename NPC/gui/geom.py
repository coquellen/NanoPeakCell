import numpy as np
from scipy.ndimage.interpolation import rotate
import os

def grep(sequence, buffer):
   return [line for line in sequence if buffer in line]

def retrieve_geom_params(lines, tile):
    results = []
    all = grep(lines, tile)
    for param in ['min_fs', 'max_fs', 'min_ss', 'max_ss', '/fs =', '/ss =', 'corner_x', 'corner_y']:
        l = grep(all,param)[0]

        results.append(l.split('=')[1].strip())
    return results

def parse_geom_file(filename, openfn=True):
    geom_params = {}
    max_fs = 0
    max_ss = 0
    if openfn:
      lines = open(filename).readlines()
    else:
      lines = filename.split('\n')
    tiles = [ line.split('/')[0] for line in lines if 'max_fs' in line ]
    for tile in tiles:
        params = retrieve_geom_params(lines, tile)
        max_fs = max(max_fs, int(params[1])+1)
        max_ss = max(max_ss, int(params[3])+1)
        geom_params[tile]= params



    return geom_params, (max_ss,max_fs)

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

        min_fs, max_fs, min_ss, max_ss = [int(p) for p in params[0:4]]

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
        #print alpha, xmin, xmax, ymin, ymax
        reconstructed[xmin:xmax, ymin:ymax] = rot

    return reconstructed[:,::-1]

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
        if len(geom_params) == 8: return DoReconstruct(data, geom_params, size=1600)

    else:
        err = 1
        msg = 'NPC is not able to handle this type of segmented detectors.\n\
               So far NPC is able to reconstruct frames from CSPAD (LCLS) and MPCCD (SACLA) detectors.\n\
               Please contact us.'
        return data


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    geom_params  = parse_geom_file('refined.geom')
    h5 = h5py.File('cxii5615_295_1430751313_868564698_laser_off.h5')
    dset = h5['data'][:]
    h5.close()
    reconstructed = reconstruct(dset, geom_params)
    plt.imshow(reconstructed, vmin=0, vmax=300, cmap='spectral')
    plt.show()