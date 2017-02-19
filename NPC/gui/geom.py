import numpy as np
from scipy.ndimage.interpolation import rotate
import h5py

def grep(sequence, buffer):
   return [line for line in sequence if buffer in line]

def retrieve_geom_params(lines, tile):
    results = []
    all = grep(lines, tile)
    for param in ['min_fs', 'max_fs', 'min_ss', 'max_ss', '/fs =', '/ss =', 'corner_x', 'corner_y']:
        l = grep(all,param)[0]

        results.append(l.split('=')[1].strip())
    return results

def parse_geom_file(filename):
    geom_params = {}
    max_fs = 0
    max_ss = 0
    lines = open(filename).readlines()

    tiles = [ line.split('/')[0] for line in lines if 'max_fs' in line ]

    for tile in tiles:
        params = retrieve_geom_params(lines, tile)
        max_fs = max(max_fs, int(params[1])+1)
        max_ss = max(max_ss, int(params[3])+1)
        geom_params[tile]= params
    return geom_params, (max_ss,max_fs)


def DoReconstruct(data, geom_params,size):
        reconstructed = np.zeros((size,size))
        
        for params in geom_params.values():
                min_fs, max_fs, min_ss, max_ss = [int(p) for p in params[0:4]]
                x = float(params[4].split('x')[0])
                y = float(params[4].split('y')[0].split('x')[1])
                data_tile = data[min_ss:max_ss+1,min_fs:max_fs+1][::-1,:]
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

                rot = rotate(data_tile, alpha)

                if int(alpha) in range(80,100):
                    reconstructed[(size / 2)-delta_y-rot.shape[0]:(size / 2)-delta_y,(size / 2)+delta_x-rot.shape[1]:(size / 2)+delta_x] = rot

                elif int(alpha) in range(175,185):
                    reconstructed[(size / 2)-delta_y:(size / 2)-delta_y+rot.shape[0],(size / 2)+delta_x-rot.shape[1]:(size / 2)+delta_x] = rot

                elif int(alpha) in range(-95,-85) or int(alpha) in range(265,275):
                    reconstructed[(size / 2)-delta_y:(size / 2)-delta_y+rot.shape[0],(size / 2)+delta_x:(size / 2)+delta_x+rot.shape[1]] = rot

                else:
                    reconstructed[(size / 2)-delta_y-rot.shape[0]:(size / 2)-delta_y,(size / 2)+delta_x:(size / 2)+delta_x+rot.shape[1]] = rot
        return reconstructed



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

