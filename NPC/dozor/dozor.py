import numpy as np
from cffi import FFI
import fabio
ffi = FFI()
ffi.cdef("""

    struct DETECTOR
    {
        int ix, iy;
        int ix_unbinned, iy_unbinned;
        int binning_factor;     
        float pixel;
    };
    
    struct DATACOL
    {
        float wave;
        float dist;
        float monoch;
        float aconst;
        int Ispot;
        float texposure;
        int mrd;
        float hmax2;
        float hmin2;
        float delh2;
        float mgain;
        float backpol[51];
        float backpolP[51];
        float backerr[51];
            
        float IMstep;

        float xcen, ycen;
        float start_angl, phiwidth;
        int number_images,image_first;
        int graph, sprint, backg, rd, isum;
        int w, wg;
        int pr;
        int prAll;
        float vbin[50];
        int pixel_min, pixel_max;
        int Kxmin, Kxmax, Kymin, Kymax;
        int nbad;
        int Bxmin[50], Bxmax[50], Bymin[50], Bymax[50];
        int wedge;
        int pLim1[1101], pLim2[1101];
        float idealback0[50];
        float idealback[150]; //50*3
            
        float RList[51051]; //51*1001
        float hklKoor[102000]; //51*1000*2
        float Ilimit[51];
        
        float vbins[51];
        float vbina[51];
        float Wil[2103]; //3*701 

        float beamstop_size;
        float beamstop_distance;
        int beamstop_vertical;
            
        float sigLev;
    };
    
    struct LOCAL
    {
        float cos2tet2[51];
        float pol[765]; //51*15
        float absorb[51];
    };
    
    struct DATACOL_PICKLE
    {
        float backpol2D[51];
        float Rfexp;       // SPOTS R-factor
        float Iav;         // SPOTS INTaver
        int NofR;          // Spots num.of
        float dlim;        // Spots Res
        double SumTotal2D, SumBack2D;
        float Coef;
        int table_suc;
        double table_sc; // Powder Scale
        double table_b; // Powder B-fac.
        float table_resol; // Powder Res.
        float table_corr; // Powder Corr.
        float table_rfact; // Powder R-factor
        float table_intsum;
    
        float table_est;      
        float score2; // Spot Score
        float score3; 
        float dlim09; // Visible resolution
    };
    
    struct Reflection
    {
        float x;
        float y;
        float intensity;
    };
    
    void dozor_set_defaults_(struct DATACOL*);
    void read_dozor_(struct DETECTOR*, struct DATACOL*, char[1024], char[1024]); 
    void pre_dozor_(struct DETECTOR*, struct DATACOL*, struct LOCAL*, char*, char*, int*);
    void dozor_do_image_(short*, struct DETECTOR*, struct DATACOL*, struct DATACOL*, struct DATACOL_PICKLE*, struct LOCAL*, char*, char*);
    void dozor_get_spot_list_(struct DETECTOR*, struct DATACOL*, struct DATACOL_PICKLE*, struct Reflection*);
    """)

#void dozor_print_version_();
#Dozor version 1.6 - From Jie
#dozorLIB = ffi.dlopen('/home/esrf/coquelle/Projects/NanoPeakCell/NPC/dozor/libdozor.so')

#Dozor version 2.0 - Compiled shared library from Nico
dozorLIB = ffi.dlopen('/home/esrf/coquelle/Downloads/dozor_NC/dozor.so')#/home/esrf/coquelle/Downloads/dozor_eiger/dozor.so')


class Dozor():
    def __init__(self, config_file=None):
        #dozorLIB.dozor_print_version_() # Only in 2.0 onwards
        self.data_input = ffi.new('struct DATACOL*')
        self.detector = ffi.new('struct DETECTOR*')
        dozorLIB.dozor_set_defaults_(self.data_input)
        # Needs to be set
        self.detector.binning_factor = 1
        

        if config_file is not None:
            fname = ffi.new('char[1024]', config_file)
            templ = ffi.new('char[1024]')
            dozorLIB.read_dozor_(self.detector, self.data_input, fname, templ)
            self.img_templ = ffi.string(templ).strip()
            self.pre_dozor()
        # This should be set at worker starter
        # and at each new data collection

        '''
        self.data_input.wave = 0.9796
        self.data_input.dist = 800.0
        self.data_input.xcen = 2097
        self.data_input.ycen = 2142
        # spot_size
        self.data_input.Ispot = 3

        # ix_min 
        self.data_input.Kxmin = 1870
        #ix_max 
        self.data_input.Kxmax = 2240
        #iy_min
        self.data_input.Kymin = 1995
        #iy_max
        self.data_input.Kymax = 4369
        '''
        # This is 2.0 and not working...
        # library is a global char constant
        # library=ffi.new('char[]',"/opt/pxsoft/dozor/v2.2.1/ubuntu20.04-x86_64/bin/xds-zcbf.so")

    def read_dozor_live(self, mxcube_dic):
        self.detector.ix_unbinned = 1475   # Pilatus 2M
        self.detector.iy_unbinned = 1679
        self.detector.ix = 1475            # Pilatus 2M
        self.detector.iy = 1679
        self.detector.pixel = 0.172000

        self.data_input.monoch = 0.990
        self.data_input.pixel_min = 0
        self.data_input.pixel_max = 64000

        self.data_input.texposure = mxcube_dic['exposure']
        self.data_input.dist = mxcube_dic['detector_distance']
        self.data_input.wave = mxcube_dic['wavelength']
        self.data_input.xcen = mxcube_dic['orgx']
        self.data_input.ycen = mxcube_dic['orgy']
        self.data_input.phiwidth = mxcube_dic['oscillation_range']
        self.data_input.start_angl = mxcube_dic['start_angle']
        self.data_input.number_images = mxcube_dic['number_images']
        self.data_input.image_first = mxcube_dic['image_first']
        self.data_input.Kxmin = 697     # Are these detector specific ?
        self.data_input.Kxmax = 1474
        self.data_input.Kymin = 790
        self.data_input.Kymax = 852

        self.data_input.Ispot = 3      # Dozor parameters to be changed
        self.data_input.sigLev = 6

        self.img_templ = mxcube_dic['template']

        self.pre_dozor()

    def pre_dozor(self):
        self.local = ffi.new('struct LOCAL*')
        detector_xy = self.detector.ix * self.detector.iy
        self.PSIim = ffi.new('char[]', detector_xy)
        self.KLim = ffi.new('char[]', detector_xy)
        debug = ffi.new('int*', 0)
        dozorLIB.pre_dozor_(self.detector, self.data_input, self.local, self.PSIim, self.KLim, debug)
        
    def do_image(self, img):
        data = ffi.new('struct DATACOL_PICKLE*')
        datacol = ffi.new('struct DATACOL*')

        dozorLIB.dozor_do_image_(ffi.cast('short*', ffi.from_buffer(img)), self.detector,
                              self.data_input, datacol, data, self.local, self.PSIim, self.KLim)

        spots = ffi.new('struct Reflection[]', data.NofR)
        dozorLIB.dozor_get_spot_list_(self.detector, datacol, data, spots)
        return data, spots
        

