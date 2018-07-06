import numpy as np
from mpi4py import MPI
from NPC.mpi.NPC_Data import mpidata
from NPC.NPC_routines import IsHit, InitDetector, Correction, AI, ROI
from NPC.NPC_IO import SaveHits as SH
from NPC.utils import get_filenames
import h5py


try:
    from psana import *
except ImportError:
    pass


comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()


class Client(object):

    def __init__(self, options):
        self.options = options
        self.detector = InitDetector(self.options)
        self.options['shape'] = self.detector.shape
        self.options['rank'] = rank
        self.roi = ROI(self.options, self.detector.shape)
        #self.MaxProj = np.zeros(self.args.detector.shape)
        self.SaveHits = SH(self.options)
        self.DataCorrection = Correction(self.options, self.detector, self.roi)
        self.Ntotal = 0
        self.Nerr = 0
        self.Nhits = 0

    def run(self):
        #Will be overwritten by the facility-dependent client
        pass

class LCLSClient(Client):

    def __init__(self, args):
        Client.__init__(self, args)
        from NPC_LCLS import ImgReshape, LaserPumpStatus
        self.args = args

        # LCLS Specific
        ds = DataSource('exp=%s:run=%s' % (args.exp, args.run))
        det = self.getDetName()

        if self.args.TimeResolved:
            LaserStatus = LaserPumpStatus()
        else: LaserStatus = None

        if self.args.SubtractBKG:
            if self.args.CrystFELGeom:
                from NPC.NPC_routines import ApplyCrystFELGeom
                self.getData = ApplyCrystFELGeom
            else:
                self.getData = det.image
        else:
            self.getData = det.calib



        #Initializing array containing data
        img = np.zeros((1480, 1552))
        root = ''
        #dark = mask = None # Need to open a dark here
        for nevent, evt in enumerate(ds.events()):

            #if nevent > 10000: break # For testing purpose only
            if nevent%(size-1)!=rank-1: continue # different ranks look at different events
            self.Ntotal += 1
            img2 = det.calib(evt)
            
            if img2 is None:
                self.Nerr += 1
                continue
            # data = self.DataCorrection.DarkCorrection(img2, self.args.roi.tuple)  # data shape 32 * 185 * 388
            # The hit is performed on the corrected image - using the provided mask
            if IsHit(self.DataCorrection.MaskCorrection(img2, self.args.roi.tuple), self.args['threshold'],
                     self.args['npixels']):

                self.Nhits += 1


                # TODO: Perform Bragg peak localization
                #id = evt.get(EventId).time()
                #root = '%s_%s_%i_%i'%(args.exp,str(args.run).zfill(3), id[0], id[1])
                #bl_info = evt.get( Bld.BldDataEBeamV7, Source('BldInfo(EBeam)'))
                energy = bl_info.ebeamPhotonEnergy()
                #          OutputFile.create_dataset("energy", data=energy)
                self.SaveHits.saveHit(img, root,energy)
                #md.addarray((root,), np.array(data), self.Ntotal, self.Nhits, self.Nerr)

                # Sending to the master
            if self.Ntotal % 10 == 0:
                    md = mpidata()
                    md.addarray((root,), np.array(img2), self.Ntotal, self.Nhits, self.Nerr)
                    md.send()
                    self.Ntotal = 0
                    self.Nhits = 0
                    self.Nerr = 0
        self.SaveHits.ClosingOpenH5()
        md.endrun()  #Should be NPC apply correction function
            #img2 -= dark * mask

                # Bkg sub and peak localization
                # NPC.getExtra()
                #SaveHits.saveHit(img)

                #md = mpidata()
                #md.addarray('img', img)
                #md.small.intensity = intensity
                #if ((nevent) % 2 == 0):  # send mpi data object to master when desired
                #    md.send()
    def getDetName(self):
        detNames = DetNames()
        for detname in detNames:
          if 'Cspad' in detname[0]:
            det=Detector(detname[0])
            break
        return det        


class SSXClient(Client):


    def __init__(self, options):
        Client.__init__(self, options)
        self.fabio = __import__('fabio')

        #This should be an object...
        if self.options['HitFile'] is None:
            self.filenames = get_filenames(self.options)
        else:
            self.filenames = self.options['HitFile'].keys()
        #These corresponds to the indexes each client will process.
        self.indexes = [i for i in range(len(self.filenames)) if (i + rank - 1) % (size - 1) == 0]


    def run(self):

        #Object used to send info to the master
        for idx in self.indexes:
            self.Ntotal += 1
            #Opening image with fabio
            img = self.fabio.open(self.filenames[idx])
            #Performing Data Correction (i.e Dark Subtraction and Azimuthal Integration - The mask is used during the Background subtraction)
            data = self.DataCorrection.DarkCorrection(img.data[self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax], self.args.roi.tuple)
            md = mpidata()

            #The hit is performed on the corrected image - using the provided mask
            if IsHit(self.DataCorrection.CorrectMask(data), self.options['threshold'], self.options['npixels']):
                self.Nhits += 1
                if self.roi.active:
                    #If a ROI was used for hit detection, getting the full-size and correct hit (dark only here)
                    data = self.DataCorrection.DarkCorrection(img.data, (0,self.detector.shape[0],0,self.detector.shape[1]))

                    #MaxProj = np.maximum(MaxProj, data)
                    # TODO: Perform Bragg peak localization


                self.SaveHits.saveHit(data, self.args.fns[idx])
                md.addarray(self.args.fns[idx], data)

                #Sending to the master
                if self.Nhits % 2 == 0:
                    md.send()
        self.SaveHits.ClosingOpenH5()
        md.endrun()



class SSX_H5_Client(SSXClient):


    def __init__(self, options):
        SSXClient.__init__(self, options)


    def visitor_func(self, name, node):
        if isinstance(node, h5py.Dataset):
            try:
                if node.shape[1] == self.detector.shape[0] and node.shape[2] == self.detector.shape[1]:
                    return node.name
            except IndexError:
                return None

    def geth5path(self, fn):
        path = None
        h5 = h5py.File(fn)
        path = h5.visititems(self.visitor_func)
        if path is not None:
            ty = h5[path].dtype
            try:
                ovl = np.iinfo(ty).max
            except ValueError:
                ovl = np.finfo(ty).max
            h5.close()
            return path, ovl, ty
        else:
            h5.close()
            return None, None, None

    def getImagesIndexes(self, N, idx):
        """This function determines the indexes of a stack of images in a given data h5 file from the Eiger.
           3 cases:
           - if a list of hits is provided
           - if shootntrap is True
           - process them all"""
        if self.options['HitFile'] is not None:
            return [int(x) for x in self.options['HitFile'][self.filenames[idx]]]
        elif self.options['shootntrap']:
            num_frames = N
            NdataH5 = int(self.filenames[idx].split('_')[-1].split('.h5')[0])
            idx_start = (NdataH5 * num_frames) % self.options['nperposition'] + self.options['nempty']
            return [i for i in range(idx_start, num_frames, self.options['nperposition'])]
        else:
            return range(N)

    def run(self):

        self.path , self.ovl, self.ty = self.geth5path(self.filenames[self.indexes[0]])
        self.detector.overload = self.ovl
        self.hitsIDX = ""
        self.nohitsIDX = ""

        for idx in self.indexes:
            #Opening h5 files
            self.h5 = h5py.File(self.filenames[idx])
            N, shape0, shape1 = self.h5[self.path].shape


            for i in self.getImagesIndexes(N, idx):
                self.Ntotal += 1
                md = mpidata()
                #Performing Data Correction (i.e Dark Subtraction and Azimuthal Integration - The mask is used during the Background subtraction)
                data = self.DataCorrection.DarkCorrection(self.h5[self.path][i,self.roi.xmin:self.roi.xmax, self.roi.ymin:self.roi.ymax])

                #The hit is performed on the corrected image - using the provided mask
                #print self.options['threshold'], self.options['npixels']
                if IsHit(self.DataCorrection.CorrectMask(data, roi = self.roi.active), self.options['threshold'], self.options['npixels']):
                    self.Nhits += 1
                    self.hitsIDX +="%s //%i\n" %(self.filenames[idx], i)
                    if self.options['roi'].lower() != 'none' and len(self.options['output_formats']) > 0:
                        #If a ROI was used for hit detection, getting the full-size and correct hit (dark only here)
                        data = self.DataCorrection.DarkCorrection(self.h5[self.path][i,::])
                        #MaxProj = np.maximum(MaxProj, data)
                        # TODO: Perform Bragg peak localization
                        self.SaveHits.saveHit(data, '%s_%i' %(self.filenames[idx].split('.h5')[0], i))
                else:
                    self.nohitsIDX += "%s //%i\n" %(self.filenames[idx], i)
                #Sending to the master
                if self.Ntotal % 100 == 0:
                    md.addarray(self.filenames[idx], data, self.Ntotal, self.Nhits, self.Nerr,(self.hitsIDX, self.nohitsIDX))
                    md.send()
                    self.Nerr = 0
                    self.Ntotal = 0
                    self.Nhits = 0
                    self.hitsIDX = ""
                    self.nohitsIDX = ""

        md.endrun()

class SACLAClient(Client):

    shutter_param = 'xfel_bl_3_shutter_1_open_valid/status'
    pump_param = ''
    energy_param = ''
    detName = ['MPCCD-8-2-001-%i'%i for i in range(1,9)]
    raw_shape = (8 * 1024 ,512)
    #rec_shape = (8 * 1024, 512)
    data = np.zeros(raw_shape,dtype=np.float64)
    #tiled = np.zeros(raw_shape, dtype=np.float64)

    def __init__(self, args):
        Client.__init__(self, args)
        self.args = args

        self.SaveHits = SH(self.args, energy=True)
        #These are the offline SACLA APIS
        self.dbpy = __import__('dbpy')
        self.stpy = __import__('stpy')

        self.bl = self.args['bl']
        self.run = self.args['run']
        ## This is SACLA specific and used in a lot of API functions
        self.taghi =  self.dbpy.read_hightagnumber(self.bl,self.run)
        self.taglist = self.dbpy.read_taglist_byrun(self.bl, self.run)

        #Getting some useful experimental info
        self.ShutterStatus = self.getShutterStatus()
        self.PumpLaserStatus = self.getPumpLaserStatus()
        self.PhotoEnergy = self.getPhotonEnergy()

        #Dealing with data retrieval  #Not sure about the tuple of run numbers ...
        self.StorageReaders = [self.stpy.StorageReader(detname,self.bl,(self.run,self.run)) for detname in self.detName]
        self.StorageBuffers = [self.stpy.StorageBuffer(SR) for SR in self.StorageReaders]

        #self.run()

    def getShutterStatus(self):
        return self.dbpy.read_syncdatalist(self.shutter_param, self.taghi, self.taglist)

    def getPumpLaserStatus(self):
        if self.args['TimeResolved']:
           return self.dbpy.read_syncdatalist(self.shutter_param, self.taghi, self.taglist)
        else:
           return None

    def getPhotonEnergy(self):
        return self.dbpy.read_syncdatalist(self.energy_param, self.taghi, self.taglist)

    def computeDark(self):
        self.dark = np.zeros(self.raw_shape,dtype=np.float64)

        i=0
        while int(self.ShutterStatus[i]) == 0:
            #Here get image of a given tag using taglist(tag)
            self.retrieveData(self.taglist[i])
            self.dark += self.data
            i+=1
        self.dark /= i+1

    def run(self):
        self.computeDark()
        self.Start = self.ShutterStatus.index('1')
        mytags = [i for i in range(self.taglist[self.Start],self.taglist[-1]+1) if (i+rank)%size == 0]

        for i,tag in enumerate(mytags):
            self.Ntotal += 1
            #Here get img
            self.retrieveData(tag)

            if IsHit(self.data - self.dark, self.args['threshold'], self.args['npixels']):
                self.Nhits += 1
                self.SaveHits.saveHit(self.data - self.dark, self.PhotoEnergy[i+self.Start],  self.PumpLaserStatus[i+self.Start])
                # Save hit (photonenergy of a given index
                # h5 - timeresolved

    #def retrieveDark(self , tag):


    def retrieveData(self,tag):

        for i in range(len(self.detName)):
            self.StorageReaders[i].collect(tag)
            self.data[i * self.raw_shape[0], (i+1) * self.raw_shape[0], :] = self.StorageBuffers[i].read_det_data() #- self.dark[i * self.raw_shape[0], (i+1) * self.raw_shape[0], :]




