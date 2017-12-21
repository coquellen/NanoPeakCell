from mpi4py import MPI
import time, os

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

import numpy as np
from NPC.mpi.NPC_Data import mpidata
from NPC.NPC_routines import InitDetector


def runmaster(nClients, args):
    t=time.time()
    detector = InitDetector(args)
    max_proj = np.zeros(detector.shape)
    Ntotal = 0
    Nhits = 0
    Nerr = 0
    txt = ""
    OutputFileName = os.path.join(args['output_directory'], 'NPC_run%s' % args['num'].zfill(3),
                                  '%s_%s' % (args['filename_root'], args['num'].zfill(3)))


    outTxtHit = open('%s.txt' % OutputFileName, 'w')
    outTxtRej = open('%s_rejected.txt' % OutputFileName, 'w')

    while nClients > 0:
        md = mpidata()
        md.recv()
        for arrinfo in md.small.arrayinfolist:
            if arrinfo.name != 'maxproj':
                try:
                    data = getattr(md, arrinfo.name[0])
                    #print "Data shape:", data.shape
                    Ntotal += arrinfo.Ntotal
                    Nhits  += arrinfo.Nhits
                    Nerr   += arrinfo.Nerr
                    txthits, txtnohits = arrinfo.hitsIDX
                    if len(txthits) > 0:
                        print >> outTxtHit, txthits
                    if len(txtnohits) > 0:
                        print >> outTxtRej, txtnohits
                    print("Processed: %5i - Hits %5i - Errors : %i"%(Ntotal, Nhits, Nerr))#md.small.Ntotal, md.small.Nhits, md
                except AttributeError:
                    print('The data from file %s have not been sent yet to the master'%arrinfo.name[0])

        if md.small.endrun:
            nClients -= 1

        if nClients == 0:
            print("Master is done")
    tf = time.time()
    print('Needed %4.2f s to lookup at %i events with %i workers'%(tf-t, Ntotal, size-1))

    outTxtRej.close()
    outTxtHit.close()


