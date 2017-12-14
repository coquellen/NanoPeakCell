import os
import sys
import importlib
import glob
import time

def Log(message):
    message = time.strftime("[%H:%M:%S] ") + message
    print(message)


def get_class(module_name, class_name):
    m = importlib.import_module(module_name)
    c = getattr(m, class_name)
    return c

def startup(options, print_function):

    presenter(print_function)
    #create_results_folders(options)
    #save_stats(options)


# ===================================================================================================================
def presenter(print_function):
    # print """                                 THIS IS THE HIT FINDING MODULE OF"""
    #if log is None:
        """            	 						        """
        print_function("""\n              ()_() v0.3.3                                                   """
        """\n  _   _       (o o)         _____           _       _____     _ _          """
        """\n | \ | |  ooO--`o'--Ooo    |  __ \         | |     / ____|   | | |         """
        """\n |  \| | __ _ _ __   ___   | |__) |__  __ _| | __ | |     ___| | |         """
        """\n | . ` |/ _` | '_ \ / _ \  |  ___/ _ \/ _` | |/ / | |    / _ \ | |         """
        """\n | |\  | (_| | | | | (_) | | |  |  __/ (_| |   <  | |___|  __/ | |         """
        """\n |_| \_|\__,_|_| |_|\___/  |_|   \___|\__,_|_|\_\  \_____\___|_|_|         """
        """\n                      By Coquelle, Goret, Burghammer and Colletier           """
        """\n"""
        """\n					""")

# ===================================================================================================================

def get_result_folder_number(options):

    results_folder = options['output_directory']


    num_folders = [int(x[-3:]) for x in glob.glob1(results_folder,"NPC_run*")]
    if len(num_folders) == 0:
        num = '1'
    else: num = str(max(num_folders)+1)
    return num

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
    root = options['filename_root']

    dir = "NPC_run%s" %num.zfill(3)
    os.mkdir(os.path.join(results_folder,dir))
    #os.mkdir(os.path.join(results_folder,dir,'MAX'))
    for output_format in options['output_formats'].split():
        os.mkdir(os.path.join(results_folder,dir,output_format.upper()))


def get_class(module_name,class_name):
    m = importlib.import_module(module_name)
    #SHould we raise some AttributeError if class does not exist
    #This should not be called if not existing anyway
    c = getattr(m, class_name)
    return c


def get_filenames(options, fns=[]):
        
        filename_root = options['filename_root']
        file_extension = options['file_extension']
        data_folder = options['data']
        live = options['live']

        f = []
        if not fns: print('Looking for files that match your parameters... Please wait')

        #Remove master files from Eiger
        if 'h5' in  file_extension:
            pattern = os.path.join(data_folder,'%s*[!master]%s'%(filename_root,file_extension))
        else:
            pattern = os.path.join(data_folder,'%s*%s'%(filename_root,file_extension))

        f = glob.glob(pattern)

        if fns:
            f = [x for x in f if x not in fns]

        if len(f) == 0 and not fns:
            if live:
                print('\n= Job progression = Hit rate =')
                return sorted(f)
            else:
                print('Sorry, no file to be processed... Yet ?')
                #return None
                sys.exit(0)

        if not fns:
            print('%i files have been found and will be processed'%len(f))
            print('\n= Job progression = Hit rate =')
        return sorted(f)

def parseHits(filename, openfn=True):
    hits = {}
    if openfn:
        f = open(filename).readlines()
    else:
        f = filename
    #with open(filename) as f:
    for line in f:
            try:
                fn, index = line.split()
                if fn in hits.keys():
                    hits[fn] += [index.strip('//')]
                else:
                    hits[fn] = [index.strip('//')]

            except ValueError:
                fn = line.strip()
                hits[fn] = 1

    return hits


