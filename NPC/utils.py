import os
import random
import sys
#import importlib

def startup(options):
    presenter()
    create_results_folders(options)
    save_stats(options)


# ===================================================================================================================
def presenter():
    # print """                                 THIS IS THE HIT FINDING MODULE OF"""
    print """            	 						        """
    print """              ()_() v0.1.0                                                   """
    print """  _   _       (o o)         _____           _       _____     _ _          """
    print """ | \ | |  ooO--`o'--Ooo    |  __ \         | |     / ____|   | | |         """
    print """ |  \| | __ _ _ __   ___   | |__) |__  __ _| | __ | |     ___| | |         """
    print """ | . ` |/ _` | '_ \ / _ \  |  ___/ _ \/ _` | |/ / | |    / _ \ | |         """
    print """ | |\  | (_| | | | | (_) | | |  |  __/ (_| |   <  | |___|  __/ | |         """
    print """ |_| \_|\__,_|_| |_|\___/  |_|   \___|\__,_|_|\_\  \_____\___|_|_|         """
    print """                      By Coquelle, Goret, Burghammer and Colletier           """
    print """ """
    print """ 					"""

# ===================================================================================================================


def check_intall(options):
    """
    SACLA: h5py
    SSX: fabio
    MPI: mpi4py
    AI: pyFAI

    :return:
    """
    pass


def create_results_folders(options):
    results_folder = options['output_directory']
    num = options['num']

    for output_format in options['output_formats'].split():
        dir = "%s_%s" %(output_format.upper(), num.zfill(3))
        os.mkdir(os.path.join(results_folder,dir))
        os.mkdir(os.path.join(results_folder,dir,'MAX'))


def get_class(module_name,class_name):
    m = importlib.import_module(module_name)
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, class_name)
    return c







def save_stats(options):
    pass

    #for format,directory in [(self.IO.H5,self.IO.H5Dir),(self.IO.pickle,self.IO.PicklesDir),(self.IO.edf,self.IO.EDFDir)]:
	#  if format:
	#    stat=open(os.path.join(self.IO.procdir,directory,'stats_%s.dat'%self.num.zfill(3)),'w')
	#    now=datetime.datetime.now()
	#    print >> stat, "Job started on  %s\n" %now
	#    print >> stat, "Job performed in directory %s" %self.IO.procdir
	#    print >> stat, "Data from %s" %self.IO.datadir
	#    print >> stat, "Files: %s*%s" %(self.IO.root,self.IO.ext)
  	#    print >> stat, "Threshold: %s" %self.HFParams.threshold
	#    print >> stat, "Minimal number of peaks in frame: %i" %self.HFParams.npixels
	#    print >> stat, "Number of procs: %i" %self.HFParams.procs
        #print >> stat, "Bkg correction: %s" %self.HFParams.DoDarkCorr
	#if self.HFParams.DoDarkCorr:
	#  print >> stat, "Bkg img: %s" %' '.join(self.IO.bname_list)
	#  print >> stat, "Number of bkg images used: %s" %self.HFParams.bkg
	#    print >> stat, "Beam X: %i" %self.XSetup.beam_x
	#    print >> stat, "Beam Y: %i" %self.XSetup.beam_y
	#    print >> stat, "Distance: %6.2f" %self.XSetup.distance
	#    print >> stat, "Wavelength: %6.3f" %self.XSetup.wavelength
	#    stat.close()

def get_files_sacla(options):
    runs = options['runs'].split(',')
    all = []
    try:
        for run in runs:
            if '-' in run:
                a, b = run.split('-')
                for i in xrange(int(a),int(b)+1):

                    all.append(str(i))
            else: all.append(run)


    except:
        pass
    data_folder = options['data']
    filenames =[]
    not_found = []
    for run in all:
        filename = os.path.join(data_folder,'%s.h5'%run)
        if os.path.isfile(filename): filenames.append(filename)
        else : not_found.append(run)
    if not_found == all:
        print 'Sorry - None of the specified runs have been found. Aborted'
        sys.exit(1)
    else:
        if not_found: print 'These specified runs were not retrieved: '+','.join(not_found)

    return filenames


def get_filenames(options):
        
        filename_root = options['filename_root']
        file_extension = options['file_extension']
        data_folder = options['data']
        randomizer = options['randomizer']

        f = []
        print 'Looking for files that match your parameters... Please wait'
        for root, dirnames, filenames in os.walk(data_folder, followlinks=True):
            for filename in filenames:
                if filename_root == None:
                    if filename.endswith(file_extension): f.append(filename)
                else:
                    if filename.endswith(file_extension) and filename.startswith(filename_root):
                        f.append(os.path.join(root, filename))
        tot = len(f)
        if tot == 0:
            print 'Sorry, no file to be processed'
            sys.exit(1)

        if randomizer not in [ 0, 'None', 'False']:

            f = random.sample(f, randomizer)
            print '%i files have been found and %i will be processed' % (tot, len(f))
        else:
            print '%i files have been found and will be processed' % tot

        return f

if __name__ == '__main__':
    options = {'runs' : '12,13,17-28',
               'data' : '/USers/nico/IBS2013/SERIALX/IRISFP'}
    get_files_sacla(options)