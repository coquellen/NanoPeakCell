import os
import sys
import importlib
import glob
import time, errno

def parseBoolString(s):
    """
    Helper function to convert string to bool
    :param s: string to be converted to bool
    :return: bool
    """
    return s.strip().lower() in ('true', 't', 'yes', '1')

def Log(message):
    """
    :param message: string
    :return: modified string with time in front of it
    """
    message = time.strftime("[%H:%M:%S] ") + message
    print(message)

def startup(options):
    presenter()

def check_input(options):
    """
    Will check the user input to make sur it is worth starting the all process...
    :param options: dictionary of options from the user input file
    :return: bool, message
    """
    # Check that the input directory file exists
    #print options['experiment']
    #print options['output_directory']
    #return True, ""
    if not os.path.exists(options['output_directory']):
        print("Output directory does not exist - Creating it")
        mkdir_p(options['output_directory'])
    if  options['experiment'] == 'SSX':
        if not os.path.exists(options['data']):
            return False, "Error: No such directory: %s" % options['data']
    elif options['shootntrap'] and options['HitFile'] is not None:
        return False, "Error: you cannot provide a hit list file with the shootntrap option turned on."
    else:
        return True, ""

def mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


# ===================================================================================================================
def presenter():
    # print """                                 THIS IS THE HIT FINDING MODULE OF"""
    #if log is None:
        """            	 						        """
        print("""\n              ()_() v0.3.3                                                   """
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
    #root = options['filename_root']

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
        # if 'h5' in  file_extension:
        #     pattern = os.path.join(data_folder,'%s*[!master]%s'%(filename_root,file_extension))
        # else:
        #     pattern = os.path.join(data_folder,'%s*%s'%(filename_root,file_extension))
        #
        # f = glob.glob(pattern)
        for root, dirnames, filenames in os.walk(data_folder, followlinks=True):
            if fns:
                filenames = [x for x in filenames if os.path.join(root, x) not in fns]

            for filename in filenames:
                if filename_root == None:
                    if filename.endswith(file_extension): f.append(filename)
                else:
                    if filename.endswith(file_extension) and filename.startswith(filename_root) and 'master.h5' not in filename:
                        f.append(os.path.join(root, filename))
        if fns:
            f = [x for x in f if x not in fns]
        if len(f) == 0 and not fns:
            if live:
                print('\n= Job progression = Hit rate =')
                return sorted(f)
            else:
                print('Sorry, no file to be processed... Yet ?\n Exiting...')
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


