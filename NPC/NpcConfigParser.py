import ConfigParser
import os.path
import glob
import sys


def parseBoolString(s):
    return s.strip().lower() in ('true', 't', 'yes', '1')

CrystFEL = {'beam_divergence': (float, 1),
            'pixel_size': (float, 100),
            'beam_bandwidth': (float, 1e-4)}

Mask = {
    'detector': (str, None),
}

Experimental_Setup = {
    'detector': (str, None),
    'wavelength': (float, None),
    'detector_distance': (float, None),
    'beam_x': (float, None),
    'beam_y': (float, None),
    'mask': (str, None)}

Hit_Finding_Parameters = {'threshold': (int, 0),
                          'npixels': (int, 20),
                          'bragg_search': (parseBoolString, False),
                          'bragg_threshold': (int, 10),
                          'roi': (str, 'none')}

General = {'experiment': (str, 'SSX'),
           'cpus': (int, 4),
           'parallelism': (str, 'multiprocessing'),
           'background_subtraction': (str, None),
           'randomizer': (int, 0),
           'live': (bool, False)}

IO_SSX = {
    'output_formats': (str, 'hdf5'),
    'file_extension': (str, None),
    'filename_root': (str, None),
    'data': (str, None),
    'output_directory': (str, '.'),
    'dark': (str, 'none')}

IO_SFX_SACLA = {'data': (str, None),
                'runs': (str, None),
                'calculte_dark': (parseBoolString, False),
                'dark_run': (int, None),
                'dark_file': (str, None),
                'output_directory': (str, None)}

IO_SFX_LCLS = {
            'experiment': (str, None),
            'run': (str, None),
            'calculte_dark': (bool, False),
            'dark_run': (int, None),
            'dark_file': (str, None),
            'output_directory': (str, None)}


class NpcGenericParser(ConfigParser.RawConfigParser):

    # mapping of configuration file sections with global dictionaries
    mapping = {'General': General,
               'Input-Output': None,
               'Hit-Finding': Hit_Finding_Parameters,
               'Experimental-Setup': Experimental_Setup
               }  # 'CrystFEL': CrystFEL}

    def __init__(self, filename):
        self.filename = filename
        ConfigParser.RawConfigParser.__init__(self)
        self.read(self.filename)

        self.get_experiment()

        for section, dic in self.mapping.iteritems():
            self.parse_section(section, dic)

        for option in ['experiment', 'parallelism', 'background_subtraction']:
            self.get_selection('General', option, True)
        self.get_selection('Input-Output', 'output_formats', False)

        # Expand all directories to absolute path
        self.get_path('Input-Output', 'data')
        self.get_path('Input-Output', 'output_directory')

    def get_path(self, dic, option):
        try:
            path = self.get(dic, option)
        except:
            return
        path = os.path.expanduser(path)  # "~toto" -> "/home/toto" "C:\User\toto"
        path = os.path.expandvars(path)  # "/xxx/$MACHIN/yyy" -> "/xxx/valeur_machin/yyy"
        path = os.path.realpath(path)    # "/x/y/../z" -> "/x/z"
        self.mapping[dic][option] = path

    def get_selection(self, dic,option, unique=False):
        opt = self.get(dic,option)
        new_option = get_param(opt)
        if unique and len(new_option) > 1:
            raise ValueError("Error. Unique selection only for option '{}'  (Your choice: {})".format(option,opt))

        else:
            self.mapping[dic][option] = ' '.join(new_option)

    def get_experiment(self):
        """
        Will determine which experiment

        """
        experiment_option = self.get('General', 'experiment')
        experiment = ' '.join(get_param(experiment_option))
        try:
            self.mapping['Input-Output'] = globals()['IO_{}'.format(experiment)]
        except KeyError:
            print 'Error. Please select only one type of experiment between SSX, SFX_SACLA and SFX_LCLS'

    def parse_section(self, section, dic):
        """
        extract all options from a section in the configuration file
        and store them in the appropriate dictionary.
        If an exception is raised regarding the value, a default value is set.
        :param section: section of the configuration file parsed
        :param dic: global dictionary to be modified
        """
        options = self.options(section)
        for option in options:
            try:
                built_in, default = dic[option]
                try:
                    dic[option] = built_in(self.get(section, option))
                except ValueError:
                    print("Exception on {0}! - Default value instead: {1}".format(option, default))
                    dic[option] = default
            except KeyError: print("Error in section {}. Option {} not recognized".format(section, option))


def get_param(s):
    """
    Takes a string in which the star (*) char is used to select an option
    Return all options selected by a star(*) in a sequence
    :param s: string
    :return: sequence
    """
    params = [sub.strip('*') for sub in s.split() if '*' in sub]
    return params

def get_result_folder_number(options):

    results_folder = options['output_directory']

    HDF5 = [int(x[-3:]) for x in glob.glob1(results_folder,"HDF5_*")]
    PICKLES = [int(x[-3:]) for x in glob.glob1(results_folder,"PICKLE_S*")]
    EDF = [int(x[-3:]) for x in glob.glob1(results_folder,"EDF_*")]
    CBF = [int(x[-3:]) for x in glob.glob1(results_folder,"CBF_*")]

    num_folders = HDF5 + EDF + PICKLES + CBF
    if len(num_folders) == 0:
        num = '1'
    else: num = str(max(num_folders)+1)
    return num


if __name__ == '__main__':

   if len(sys.argv) != 2:
    print 'Usage: npc config-file'

   else:
    config_file = sys.argv[1]
    options = {}

    options['config_file'] = config_file
    npc_parser = NpcGenericParser(config_file)

    for key in npc_parser.mapping:
        options.update(npc_parser.mapping[key])

    options['num'] = get_result_folder_number(options)
    #print options

    if options['parallelism'] == 'MPI':
        from NPC.PreProcessing import DataProcessing_MPI as DataProc
    else:
        from NPC.PreProcessing import DataProcessing_multiprocessing as DataProc
    DataProc(options)
