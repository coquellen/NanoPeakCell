import multiprocessing
from NPC.HitFinder import HitFinder
import fabio
import h5py

class MProcess(multiprocessing.Process):

    def __init__(self, task_queue, result_queue, options, detector, ai):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.options = options
        self.detector = detector
        self.ai = ai
        self.signal = True
        self.HitFinder = HitFinder(self.options, self.detector, self.ai)
        self.data_mapping = {'SSX': self.set_data_ssx, 'SFX_SACLA': self.set_data_sacla}
        self.h5 = None
        self.h5_filename = None
        #if PUBSUB: pub.subscribe(self.OnStop, 'StopThreads')

    def run(self):

        while self.signal:
            next_task = self.task_queue.get()
            if next_task is None:
                self.task_queue.task_done()
                if self.h5 is not None: self.h5.close()
                break
            else:
                result = self.data_mapping[self.options['experiment']](next_task)
            self.result_queue.put(result)
            self.task_queue.task_done()
        return

    def set_data_ssx(self,filename):
        if 'eiger' in self.options['detector'].lower():
            return self.set_data_eiger(filename)
        else:
            self.HitFinder.data = fabio.open(filename).data
            return self.HitFinder.get_hit(filename)

    def set_data_eiger(self,task):
        filename, group, index = task
        if self.h5 == None:
            self.h5 = h5py.File(filename)
            self.h5_filename = filename
        if filename != self.h5_filename:
            self.h5.close()
            self.h5 = h5py.File(filename)
            self.h5_filename = filename
        self.HitFinder.data = self.h5['entry/%s'%group][index,::]
        return self.HitFinder.get_hit(task)

    def set_data_sacla(self,task):
        filename, run, tag = task
        if self.h5 == None:
            self.h5 = h5py.File(filename)
            self.h5_filename = filename
        if filename != self.h5_filename:
            self.h5.close()
            self.h5 = h5py.File(filename)
            self.h5_filename = filename
        self.HitFinder.data = self.h5['%s/detector_2d_assembled_1/tag_%s/detector_data'%(run,tag)][:]
        return self.HitFinder.get_hit((run,tag))


    def OnStop(self):
        try:
            self.signal = False
        except:
            return

