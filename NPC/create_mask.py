#[General]
#experiment = *SSX SFX_SACLA SFX_LCLS
#parallelism= MPI *multiprocessing
import multiprocessing
import numpy as np
import h5py
import pyFAI

class MProcess(multiprocessing.Process):

    def __init__(self, detector, filename, index,total, cpus, threshold,results):        
        multiprocessing.Process.__init__(self)
        self.mask = detector.mask
        self.rank = index
        self.size = cpus
        self.threshold = threshold
        self.results = results
        self.myindexes = [j for j in xrange(total) if (j+self.rank)%self.size==0]
        self.h5=h5py.File(filename)
        
    def run(self):
        for index in self.myindexes:
               self.data = self.h5['entry/data_000001'][index,::]
               self.mask [ self.data >= self.threshold ] = 1
               if index % 100 == 0: print self.rank, index, self.mask.sum()


        self.results.put(self.mask)
cpus = 8
detector = pyFAI.detectors.Detector.factory('Eiger4M')

#[Input-Output]
filename = '/data/opid13/inhouse/EIGER_DATA_1/TRANSFER/_tmp/nerorun_BOOT_003_C_local/series_100_master.h5'

maskout = 'Eiger_mask_20150403.edf'
threshold = 1000


results = multiprocessing.Queue()

consumers = [ MProcess( detector, filename, i, 1000, cpus, threshold, results) for i in xrange(cpus)]
for w in consumers:
            w.start()
#for w in consumers:
#    w.join()
mask = detector.mask
i = 0
while i != cpus:
   i +=1
   temp = results.get()
   mask [temp == 1] = 1
   print i
print mask.sum()


out = h5py.File(maskout)
out.create_dataset('data', data = mask, dtype='uint16')
out.close()
