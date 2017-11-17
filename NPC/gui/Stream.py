import os
import sys
import numpy as np

sys.path.insert(0, '../gui/')
#sys.path.insert(0, '../gui/')
from geom import parse_geom_file, reconstruct, getGeomTransformations
from NPC import utils
from PyQt4.QtCore import QThread, QObject, pyqtSignal
def parse_stream(streamfile):
        append = 0
        crystal = 0
        count_shots = 0
        count_crystals = 0
        frame_stream = []
        frames = []
        head_check = 0
        header = ''
        geom = Geom()
        stream = open(streamfile)
        all_reflections = []
        REFLECTIONS = 0
        PEAKS = 0
        GEOM_FLAG = 0
        geom = ''
        filenames = []
        indexed = []


        for index, line in enumerate(stream):
            ### GEt header
            while (head_check == 0):

                header += line
                if '----- Begin geometry file -----' in line: GEOM_FLAG = 1

                if GEOM_FLAG: geom += line

                #if GEOM_FLAG:
                #    if line.startswith('clen'):
                #        #print line.split('=')
                #        geom.distance = float(line.split('=')[1].split(';')[0].strip())
                #    if 'corner_x' in line:
                #        geom.bx = -1 * float(line.split('=')[1].split(';')[0].strip())
                #    if 'corner_y' in line:
                #        geom.by = -1 * float(line.split('=')[1].split(';')[0].strip())
                #    if 'res' in line:
                #        geom.ps = 1 / float(line.split('=')[1].split(';')[0].strip())
                #    if 'photon_energy' in line:
                #        geom.energy = float(line.split('=')[1].split(';')[0].strip())
                #        geom.wl = 12398.425 / geom.energy
                #    if 'max_fs' in line:
                #        geom.max_fs = float(line.split('=')[1].split(';')[0].strip())
                #    if 'max_ss' in line:
                #        geom.max_ss = float(line.split('=')[1].split(';')[0].strip())

                if '----- End geometry file -----' in line: GEOM_FLAG = 0
                break

            ### Get beginning of an image
            if 'Begin chunk' in line:
                count_shots += 1
                append = 1
                head_check = 1
                # frame_stream.append(l)


            ### If
            elif 'Image filename' in line:
                frame = Frame()
                frame.filename = line.split()[2].strip()
                filenames.append(frame.filename)

            # The division by 10 is to convert from nm-1 to Angstrom-1
            elif 'indexed_by' in line:
                if 'none' not in line:
                    count_crystals += 1
                    crystal = 1
                    frame.indexing = line.split()[2].strip()
                    indexed.append(frame.filename)
                else:
                    frame.indexing = 'none'

                #SACLA specific - not needed
                # try:
                #    f = os.path.split(filename)[1]
                #    tag = os.path.splitext(f)[0].split('tag_')[1]
                #    frame.timeline = tag
                #except:
                #    pass

            elif 'diffraction_resolution_limit' in line:
                res = float(line.split()[5])
                frame.res = res

            elif 'Cell parameters' in line:
                a0, b0, c0 = line.split()[2:5]
                frame.a = float(a0)
                frame.b = float(b0)
                frame.c = float(c0)
            elif 'astar' in line:
                x, y, z = line.split()[2:5]
                frame.astar[0] = float(x) / 10
                frame.astar[1] = float(y) / 10
                frame.astar[2] = float(z) / 10

            elif 'bstar' in line:
                x, y, z = line.split()[2:5]
                frame.bstar[0] = float(x) / 10
                frame.bstar[1] = float(y) / 10
                frame.bstar[2] = float(z) / 10

            elif 'cstar' in line:
                x, y, z = line.split()[2:5]
                frame.cstar[0] = float(x) / 10
                frame.cstar[1] = float(y) / 10
                frame.cstar[2] = float(z) / 10

            elif 'End of reflections' in line:
                REFLECTIONS = 0

            elif 'End of peak list' in line:
                PEAKS = 0

            elif "End chunk" in line:
                if crystal == 1:
                    #frame_stream.append(line)
                    #frame.all = frame_stream
                    frames.append(frame)
                append = 0
                frame_stream = []
                crystal = 0

            if REFLECTIONS:
                h, k, l, I, SIG, P, BKG, X, Y = line.split()[0:9]
                # bkg, x, y = line.split()[6:9]
                # SNR = float(line.split()[3]) / float(line.split()[4])
                frame.reflections.append([int(h), int(k), int(l), float(I), float(SIG), float(BKG), float(X),
                                        float(Y)])  # geom.get_resolution(float(x), float(y)) ])
                #frame.hkl_stream.append(line)



            #if append == 1: frame_stream.append(line)
            if PEAKS:
                X, Y, RES, I, panel = line.split()
                frame.peaks.append([float(X), float(Y),float(RES), float(I), str(panel)])
            if '  h    k    l          I   sigma(I)' in line:
                REFLECTIONS = 1
                #append = 0
            if '  fs/px   ss/px (1/d)/nm^-1   Intensity' in line:
                PEAKS = 1


            #if count_shots % 1000 == 0: print '%7i frames parsed, %7i crystals found\r' % (count_shots, count_crystals),
            sys.stdout.flush()

        #print '%7i frames parsed, %7i crystals found\r' % (count_shots, count_crystals),
        #sys.stdout.flush()
        #print

        return header, frames, geom, all_reflections


class CrystFELStream(QObject):

    update = pyqtSignal(list)
    sendGEOM = pyqtSignal(str)
    finished = pyqtSignal()
    info = pyqtSignal(tuple)

    def __init__(self, streamfile, mainThread):
        super(CrystFELStream, self).__init__()
        self.streamfile = streamfile
        self.mainThread = mainThread

    def parse_stream(self):
        crystal = 0
        count_shots = 0
        count_crystals = 0
        self.frames = []
        self.header = ''
        geom = Geom()
        stream = open(self.streamfile)
        all_reflections = []
        head_check = 0
        REFLECTIONS = 0
        PEAKS = 0
        GEOM_FLAG = 0
        self.geom = ''
        self.filenames = []
        self.indexed = []
        emit = 0


        for index, line in enumerate(stream):
            prt = 0
            ### GEt header
            while (head_check == 0):

                self.header += line
                if '----- Begin geometry file -----' in line: GEOM_FLAG = 1

                if GEOM_FLAG: self.geom += line

                # if GEOM_FLAG:
                #    if line.startswith('clen'):
                #        #print line.split('=')
                #        geom.distance = float(line.split('=')[1].split(';')[0].strip())
                #    if 'corner_x' in line:
                #        geom.bx = -1 * float(line.split('=')[1].split(';')[0].strip())
                #    if 'corner_y' in line:
                #        geom.by = -1 * float(line.split('=')[1].split(';')[0].strip())
                #    if 'res' in line:
                #        geom.ps = 1 / float(line.split('=')[1].split(';')[0].strip())
                #    if 'photon_energy' in line:
                #        geom.energy = float(line.split('=')[1].split(';')[0].strip())
                #        geom.wl = 12398.425 / geom.energy
                #    if 'max_fs' in line:
                #        geom.max_fs = float(line.split('=')[1].split(';')[0].strip())
                #    if 'max_ss' in line:
                #        geom.max_ss = float(line.split('=')[1].split(';')[0].strip())

                if '----- End geometry file -----' in line:
                    GEOM_FLAG = 0
                    self.sendGEOM.emit(self.geom)
                break

            ### Get beginning of an image
            if 'Begin chunk' in line:
                count_shots += 1
                append = 1
                head_check = 1
                # frame_stream.append(l)


            ### If
            elif 'Image filename' in line:
                frame = Frame()
                frame.filename = line.split()[2].strip()
                self.filenames.append(frame.filename)

            # The division by 10 is to convert from nm-1 to Angstrom-1
            elif 'indexed_by' in line:
                if 'none' not in line:
                    count_crystals += 1
                    crystal = 1
                    frame.indexing = line.split()[2].strip()
                    self.indexed.append(frame.filename)
                else:
                    frame.indexing = 'none'

            elif 'diffraction_resolution_limit' in line:
                res = float(line.split()[5])
                frame.res = res

            elif 'Cell parameters' in line:
                a0, b0, c0 = line.split()[2:5]
                frame.a = float(a0)
                frame.b = float(b0)
                frame.c = float(c0)
            elif 'astar' in line:
                x, y, z = line.split()[2:5]
                frame.astar[0] = float(x) / 10
                frame.astar[1] = float(y) / 10
                frame.astar[2] = float(z) / 10

            elif 'bstar' in line:
                x, y, z = line.split()[2:5]
                frame.bstar[0] = float(x) / 10
                frame.bstar[1] = float(y) / 10
                frame.bstar[2] = float(z) / 10

            elif 'cstar' in line:
                x, y, z = line.split()[2:5]
                frame.cstar[0] = float(x) / 10
                frame.cstar[1] = float(y) / 10
                frame.cstar[2] = float(z) / 10

            elif 'End of reflections' in line:
                REFLECTIONS = 0

            elif 'End of peak list' in line:
                PEAKS = 0

            elif "End chunk" in line:
                prt = 1
                if crystal == 1:
                    # frame_stream.append(line)
                    # frame.all = frame_stream
                    self.frames.append(frame)
                crystal = 0

            if REFLECTIONS:
                h, k, l, I, SIG, P, BKG, X, Y, panel = line.split()[0:10]
                frame.reflections.append([int(h), int(k), int(l), float(I), float(SIG), float(BKG), float(X),
                                          float(Y), str(panel)])  # geom.get_resolution(float(x), float(y)) ])
                # frame.hkl_stream.append(line)

            # if append == 1: frame_stream.append(line)
            if PEAKS:
                X, Y, RES, I, panel = line.split()
                frame.peaks.append([float(X), float(Y), float(RES), float(I), str(panel)])

            if '   h    k    l          I   sigma(I)' in line:
                REFLECTIONS = 1
                # append = 0
            if '  fs/px   ss/px (1/d)/nm^-1   Intensity' in line:
                PEAKS = 1

            if count_shots % 500 == 0 and count_shots > 0 and prt == 1:
                prt = 0
                print('%7i frames parsed, %7i crystals found' % (count_shots, count_crystals))
                if emit == 0:
                    self.update.emit([self.filenames, self.indexed])
                emit += 1
                if emit % 4 == 0:
                    self.info.emit((count_shots, count_crystals))
            sys.stdout.flush()


        print('%7i frames parsed, %7i crystals found\r' % (count_shots, count_crystals))
        #sys.stdout.flush()
        self.info.emit((count_shots, count_crystals))
        self.moveToThread(self.mainThread)
        self.finished.emit()
        self.update.emit([self.filenames, self.indexed])



        #return header, frames, geom, all_reflections

    def sort(self, attribute, length=None, max_res=None):
        if attribute == 'res': return self.sortbyres(length, max_res)
        if attribute == 'a':
            if length == None:
                return sorted(self.frames, key=lambda x: x.a)
            else:
                length = min(length, len(self.frames))
                return sorted(self.frames, key=lambda x: x.res)[0:length]
        if attribute == 'b':   return sorted(self.frames, key=lambda x: x.b)
        if attribute == 'c':   return sorted(self.frames, key=lambda x: x.c)
        if attribute == 'name': self.frmes_res = sorted(self.frames, key=lambda x: x.filename)

    def sortByRes(self, length, max_res):
        if length is None:
            if max_res is None:
                self.frames_res = sorted(self.frames,
                                         key=lambda x: x.res)  # return sorted(self.frames, key=lambda x: x.res)
            else:
                self.frames_res = sorted([i for i in self.frames if i.res <= max_res], key=lambda x: x.res)
        if max_res == None:
            length = min(length, len(self.frames))
            self.frames_res = sorted(self.frames, key=lambda x: x.res)[0:length]
        else:
            length = min(length, len(nl))
            self.frames_res = sorted([i for i in self.frames if i.res <= max_res], key=lambda x: x.res)[:length]

    def bkg_stats(self,maxres, bins):
        self.bins = self.geom.get_bins(maxres, bins)[::-1]


        mean = []
        std=[]
        TOFIX = []
        for i in range(self.bins.size):
            if i == self.bins.size - 1:
                rmax = 50
            else:
                rmax = self.bins[i + 1]
            rmin = self.bins[i]
            BKG = self.all_reflections[:,5]
            RES = self.geom.get_resolution(self.all_reflections[:,6], self.all_reflections[:,7])
            idx = np.where( (RES <= rmax) & ( RES >= rmin))
            IR0 = BKG[idx]
            m = IR0.mean()
            s = IR0.std()

            mean.append(m)
            std.append(s)
            message = ""
            if s > m:
                message = " -- WORRISOME !! -- "
                TOFIX.append(True)
            else:
                message = ""
                TOFIX.append(False)
            print("Shell %4.2f - %4.2f : %4.2f +/- %4.2f %s" % (rmax, rmin, IR0.mean(), IR0.std(), message))

    def truncate(self,start,stop,filename):
        with open(filename,'w') as f:
            f.write(self.header)
            count = start
            while count <= stop-1:
                f.write(''.join(self.frames[count].all))
                count += 1

    def saveRes(filename):
        pass

    def selectIndexingMethods(self, *args):
        self.indexing = []
        for meth in args:
            self.indexing += [f for f in self.frames if f.indexing == meth]

    def saveIndexed(self, filename):
        if not hasattr(self, 'indexing'):
            print('Please select the different indexing methods to be saved with "select_indexing_methods"')
            return
        else:
            out = open(filename, 'w')
            print >> out, self.header,
            for f in self.indexing:
                print >> out, ''.join(f.all),
            print('New stream saved in file %s' % filename)

    def saveIndividual(self):
        for f in self.frames:
            root = f.filename.split('.h5')[0]
            out = open(root + '.stream', 'w')
            print >> out, self.header
            print >> out, ''.join(f.all)

    def saveTruncate(self, root, n):
        total = len(self.frames)
        chunk = total / n
        i = 0 
        num = total
        for i in range(0,n):#while i < n:
            fout = '%s_%i.stream'%(root,num)
            print('Saving %s' %fout)
            out = open(fout, 'w')
            print >> out, self.header,
            for i in range(0,num):
                print >> out, ''.join(self.frames[i].all),
            out.close()
            num -= chunk
            i += 1

    def saveFilenames(self, filenames,filename):
        out = open(filename, 'w')
        print >> out, self.header,
        for frame in self.frames:
            if frame.filename in filenames: print >> out, ''.join(f.all)
        out.close()

    def selectCell(self, a, b, c, da, db, dc):
        if not hasattr(self, 'a'): self.a = np.array([f.a for f in self.frames])
        if not hasattr(self, 'b'): self.b = np.array([f.b for f in self.frames])
        if not hasattr(self, 'c'): self.c = np.array([f.c for f in self.frames])
        indices_a = np.where(np.logical_and(self.a > a - da, self.a <= a + da))
        indices_b = np.where(np.logical_and(self.b[indices_a] > b - db, self.b[indices_a] <= b + db))
        indices_c = np.where(np.logical_and(self.c[indices_b] > c - dc, self.c[indices_b] <= c + dc))
        temp_indices = [indices_b[0][i] for i in indices_c[0]]
        self.final_indices = [indices_a[0][i] for i in indices_c[0]]
        print('%i crystals out of %i have been selected ' % (len(self.final_indices), len(self.frames)))
        print('To save a new stream with these cell parameters distribution: please use save_cell("out.stream)"')

    # final_indices

    def getStats(self, time=False, plot=False, nbins=20, time_binning=1000):
        if time == True:
            out = open("time_stats.txt", 'w')
            threshold = time_binning
            if threshold == 1: threshold = 2
            nl = sorted(self.frames, key=lambda x: x.timeline)
            i = 0
            while ( i + threshold < len(nl)):
                t = []
                res = []
                a = []
                b = []
                c = []
                for i in range(i, i + threshold):
                    t.append(int(self.frames[i].timeline))
                    res.append(self.frames[i].res)
                    a.append(self.frames[i].a)
                    b.append(self.frames[i].b)
                    c.append(self.frames[i].c)

                t = np.array(t)
                res = np.array(res)
                a = np.array(a)
                b = np.array(b)
                c = np.array(c)
                print >> out, '%10i %7.4f %7.4f %7.4f%7.4f%7.4f %7.4f %7.4f%7.4f' % (np.average(t),
                                                                                     np.average(res),
                                                                                     np.std(res),
                                                                                     np.average(a),
                                                                                     np.std(a),
                                                                                     np.average(b),
                                                                                     np.std(b),
                                                                                     np.average(c),
                                                                                     np.std(c))

        else:
            self.res = np.array([f.res for f in self.frames])
            print(np.min(self.res), np.max(self.res), np.median(self.res))
            hist_res = np.histogram(self.res, bins=nbins, range=(np.min(self.res), np.max(self.res)))
            if plot == True:
                self.plot(hist_res)
            self.a = np.array([f.a for f in self.frames])
            self.b = np.array([f.b for f in self.frames])
            self.c = np.array([f.c for f in self.frames])
            print('cell param a - min: %6.2f - max: %6.2f - median: %6.2f' % (
                self.a.min(), self.a.max(), np.average(self.a)))
            print('cell param b - min: %6.2f - max: %6.2f - median: %6.2f' % (
                self.b.min(), self.b.max(), np.average(self.b)))
            print('cell param c - min: %6.2f - max: %6.2f - median: %6.2f' % (
                self.c.min(), self.c.max(), np.average(self.c)))


    def saveCell(self, filename):
        if not hasattr(self, 'final_indices'):
            print('Please select a new distribution of cell parameters with select_cell')
            return
        else:
            out = open(filename, 'w')
            print >> out, self.header,
            for index in self.final_indices:
                print >> out, ''.join(self.frames[index].all),
            print('New stream saved in file %s' % filename)

    def saveReciprocalSpace(self, filename):
        with open(filename,'w') as fout:
            for f in self.frames:
                fout.write('%s %-11.7f %-11.7f %-11.7f %-11.7f %-11.7f %-11.7f %-11.7f %-11.7f %-11.7f\n'%(f.filename, f.astar[0], f.astar[1], f.astar[2], f.bstar[0], f.bstar[1], f.bstar[2], f.cstar[0], f.cstar[1], f.cstar[2]))


    #def plot(self, his):
    #    hist, bins = his
    #    width = 0.7 * (bins[1] - bins[0])
    #    center = (bins[:-1] + bins[1:]) / 2
    #    plt.bar(center, hist, align='center', width=width)
    #    plt.show()



class Frame(object):
    def __init__(self):
        self.a = 0
        self.b = 0
        self.c = 0
        self.alpha = 90.
        self.beta = 90.
        self.gamma = 90.
        self.res = 5.
        self.index = 'none'
        self.filename = 'example.h5'
        self.timeline = 0
        self.indexing = ''
        self.astar = np.zeros((3,))
        self.bstar = np.zeros((3,))
        self.cstar = np.zeros((3,))
        self.reflections = []
        self.peaks = []
        self.filenames = []
        self.indexed = []
        self.hkl_stream = []

class Geom(object):
    def __init_(self):
        self.distance = 0
        self.energy = 0
        self.wl = 0
        self.bx = 0
        self.by = 0
        self.ps = 0
        self.RADIUS = 0
        self.RES = 0
        self.max_fs = 0
        self.max_ss = 0

    def get_resolution(self, x, y):
        dx = (x - self.bx) * self.ps
        dy = (y - self.by) * self.ps
        radius = np.sqrt(dx ** 2 + dy ** 2)
        theta = 0.5 * np.arctan(radius / self.distance)
        return self.wl / (2. * np.sin(theta))

    def get_maxres(self):
        #TODO: needs to be adapted for CSPAD or MPCCD
        x1, y1 = 0, 0
        d1 = np.sqrt( (x1 - self.bx ) ** 2 + (y1 - self.by) ** 2)
        x2, y2 = self.max_fs, self.max_ss
        d2 = np.sqrt((x2 - self.bx) ** 2 + (y2 - self.by) ** 2)
        x3, y3 = self.max_fs, 0
        d3 = np.sqrt((x3 - self.bx) ** 2 + (y3 - self.by) ** 2)
        x4, y4 = 0, self.max_ss
        d4 = np.sqrt((x4 - self.bx) ** 2 + (y4 - self.by) ** 2)

        d = max(d1, d2, d3, d4)
        theta = 0.5 * np.arctan( d * self.ps / self.distance)
        return (d, self.wl / (2. * np.sin(theta)))

    def get_bins(self, maxres, nbins):
        RADIUS, RES = self.get_maxres()
        if maxres < RES:
            print("Sorry. Given the geometry, highest resolution is %4.2f"%RES)
            maxres = RES
            RMAX = RADIUS
        else:
            theta =  np.arcsin(self.wl / (2 * maxres))
            RMAX = np.tan(2 * theta) * self.distance / self.ps
        S = np.pi * RMAX ** 2 / float(nbins)
        radius = np.sqrt(np.arange(1, nbins+1, 1) * S / np.pi) * self.ps
        theta = 0.5 * np.arctan(radius / self.distance)
        self.bins = self.wl / (2. * np.sin(theta))
        return self.bins
        #print self.bins

if __name__ == "__main__":

    #s=Stream('iris_nobkgsub_zaef_rings_nocen.stream')
    s = Stream('dev/C_RS_clean.stream')
    geom_params = parse_geom_file(s.geom, openfn=False)
    import h5py
    data = h5py.File('dev/HDF5/HDF5_cxip12715_r0051_016/cxip12715_51_1499479169_79177848.h5')['data'][:]



    DetTransfo = getGeomTransformations(geom_params[0])
    idx = 0
    size = geom_params[0][geom_params[0].keys()[0]]
    ss = int(size[1]) - int(size[0]) + 1
    fs = int(size[3]) - int(size[2]) + 1

    peaks = s.frames[idx].peaks
    from scipy.ndimage.interpolation import rotate
    from matplotlib.patches import Circle

    panels = [item[-1] for item in peaks]
    patches = []

    for panel in geom_params[0].keys():

        idx = [i for i in range(len(panels)) if panels[i] == panel]
        if len(idx) > 0:

            alpha, xmin, xmax, ymin, ymax, deltaY, deltaX = DetTransfo[panel]

            print("Panel %s: coordinates should be comprised between:\n" \
                  "xmin = %5i and xmax = %5i \n" \
                  "ymin = %5i and xmax = %5i "%(panel, xmin, xmax, ymin, ymax))
            shiftX = int(geom_params[0][panel][1])
            shiftY = int(geom_params[0][panel][3])

            X = np.array([shiftX - ss/2. - float(peaks[i][0]) for i in idx])
            Y = np.array([shiftY - fs/2. - float(peaks[i][1]) for i in idx])
            theta = np.radians(alpha)
            c, s = np.cos(theta), np.sin(theta)
            X1 = X * c - Y * s
            Y1 = X * s + Y * c

            for index, x in np.ndenumerate(X1):
                x1 = Y1[index] + xmin
                y1 = X1[index] + ymin
                circle = Circle((x1, y1), 0.1)
                patches.append(circle)
                print(Y1[index] + xmin, X1[index] + ymin)


    from matplotlib import pyplot as plt
    from matplotlib.collections import PatchCollection
    fig, ax = plt.subplots()
    p = PatchCollection(patches, alpha=0.4)
    colors = 100*np.random.rand(len(patches))
    ax.add_collection(p)
    p.set_array(np.array(colors))
    plt.show()





    #plt.imshow(reconstructed)
    #plt.show()


