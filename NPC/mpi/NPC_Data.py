import numpy as np
from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

class arrayinfo(object):
    def __init__(self,name,array, Ntotal, Nhits, Nerr, hitsIDX):
        self.name = name
        self.shape = array.shape
        self.dtype = array.dtype
        self.Ntotal = Ntotal
        self.Nhits = Nhits
        self.Nerr = Nerr
        self.hitsIDX = hitsIDX

class small(object):
    def __init__(self):
        self.arrayinfolist = []
        self.endrun = False
    def addarray(self,name,array, Ntotal, Nhits, Nerr, hitsIDX):
        self.arrayinfolist.append(arrayinfo(name,array, Ntotal, Nhits, Nerr, hitsIDX))

class mpidata(object):

    def __init__(self):
        self.small=small()
        self.arraylist = []

    def endrun(self):
        self.small.endrun = True
        comm.send(self.small,dest=0,tag=rank)

    def addarray(self,name,array, Ntotal, Nhits, Nerr, hitsIDX):
        self.arraylist.append(array)
        self.small.addarray(name,array, Ntotal, Nhits, Nerr, hitsIDX)

    def send(self):
        assert rank!=0
        comm.send(self.small,dest=0,tag=rank)
        for arr in self.arraylist:
            assert arr.flags['C_CONTIGUOUS']
            comm.Send(arr,dest=0,tag=rank)

    def recv(self):
        assert rank==0
        status=MPI.Status()
        self.small=comm.recv(source=MPI.ANY_SOURCE,tag=MPI.ANY_TAG,status=status)
        recvRank = status.Get_source()
        if not self.small.endrun:
            for arrinfo in self.small.arrayinfolist:
                if not hasattr(self,arrinfo.name[0]) or arr.shape!=arrinfo.shape or arr.dtype!=arrinfo.dtype:
                    setattr(self,arrinfo.name[0],np.empty(arrinfo.shape,dtype=arrinfo.dtype))

                arr = getattr(self,arrinfo.name[0])
                comm.Recv(arr,source=recvRank,tag=MPI.ANY_TAG)


#class mpistats(object):
#    def __init__(self):
#        self.small = small()
#        self.arraylist = []

