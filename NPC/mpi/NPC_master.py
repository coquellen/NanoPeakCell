from mpi4py import MPI
import time, os

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

from NPC.mpi.NPC_Data import mpidata
import subprocess, shutil

def runmaster(nClients, args):
    t=time.time()
    #detector = InitDetector(args)
    #max_proj = np.zeros(detector.shape)
    Ntotal = 0
    Nhits = 0
    Nerr = 0
    txt = ""
    #OutputFileName = os.path.join(args['output_directory'], 'NPC_run%s' % args['num'].zfill(3),
    #                              'hits_%s' % (args['num'].zfill(3)))


    #outTxtHit = open('%s.txt' % OutputFileName, 'w')
    #outTxtRej = open('%s_rejected.txt' % OutputFileName, 'w')
    md = mpidata()

    while nClients > 0:
        md.recv()
        for arrinfo in md.small.arrayinfolist:
            if arrinfo.name != 'maxproj':
                try:
                    data = getattr(md, arrinfo.name[0])
                    #print "Data shape:", data.shape
                    Ntotal += arrinfo.Ntotal
                    Nhits  += arrinfo.Nhits
                    Nerr   += arrinfo.Nerr
                    #txthits, txtnohits = arrinfo.hitsIDX
                    #if len(txthits) > 0:
                    #    outTxtHit.write(txthits)
                    #if len(txtnohits) > 0:
                    #    outTxtHit.write(txthits)print >> outTxtRej, txtnohits
                    print("Processed: %5i - Hits %5i - Errors : %i"%(Ntotal, Nhits, Nerr))#md.small.Ntotal, md.small.Nhits, md
                except AttributeError:
                    print('The data from file %s have not been sent yet to the master'%arrinfo.name[0])

        if md.small.endrun:
            nClients -= 1

        if nClients == 0:
            print("Master is done")
    tf = time.time()
    print('Needed %4.2f s to lookup at %i events with %i workers'%(tf-t, Ntotal, size-1))

    if args['crystfel']:
        #Should we loop over ranks ??
        if args['TimeResolved']:
            for laser in ['on', 'off']:
                #OutputFilename = os.path.join(self.args['output_directory'],
                #                              'NPC_run%s' % self.args['num'].zfill(3),

                cryst_dir = os.path.join (args['output_directory'], 'NPC_run%s' % args['num'].zfill(3), 'CRYSTFEL_%s' % laser)
                #cryst_dir = os.path.join(IO.procdir, IO.H5Dir, 'CRYSTFEL_%s' % laser)
                os.mkdir(cryst_dir)
                os.chmod(cryst_dir, 777)
                # Copy input files to this dir
                root_dir = '/home/coquelle/CRYSTFEL_FILES/'
                files = ['current.geom', 'current.pdb', 'index.csh', 'stats.csh', 'flauncher.csh']
                for f in files:
                    _f = os.path.join(root_dir, f)
                    shutil.copy(_f, cryst_dir)

                os.chdir(cryst_dir)
                h5path = os.path.join(args['output_directory'], 'NPC_run%s' % args['num'].zfill(3), 'HDF5')
                subprocess.call(
                    "csh flauncher.csh %s %s *%s.h5" % (h5path, "%s_%s" % (args['run'], laser), laser),
                    shell=True)
        else:

            #cryst_dir = os.path.join(IO.procdir, IO.H5Dir, 'CRYSTFEL')
            cryst_dir = os.path.join(args['output_directory'], 'NPC_run%s' % args['num'].zfill(3), 'CRYSTFEL')
            os.chdir(cryst_dir)
            h5path = os.path.join((args['output_directory'], 'NPC_run%s' % args['num'].zfill(3), 'HDF5'))
            subprocess.call("csh flauncher.csh %s %s *.h5" % (h5path, "%s" % (args['run'])), shell=True)


            #outTxtRej.close()
    #outTxtHit.close()


