import os,numpy as np

def readheader(header,filename):
    fname ,fileExtension=os.path.splitext(filename)
    if fileExtension == '.mar3450':
       bx = header['CENTER_X']
       by = header['CENTER_Y']
       wl = header['WAVELENGTH']
       psx= header['PIXEL_LENGTH']
       psy= header['PIXEL_HEIGHT']
       distance = header['DISTANCE']
       return distance, psx, psy, wl, bx, by
    
    if fileExtension == '.cbf':
        header=header['_array_data.header_contents'].split('\n')
        for setting in header:
            if 'Pixel_size' in setting:
            #Conversion from meter to um
                psx=str(np.float(setting.split()[2])*1000000)
                psy=str(np.float(setting.split()[5])*1000000)
         
            if 'Detector_distance' in setting:
                #Conversion from meter to um
	            distance=str(float(setting.split()[2])*1000)
         
            if 'Beam_xy' in setting:
                by,bx=setting[setting.find("(")+1:setting.find(")")].split(',')
                bx=bx.strip()
                by=by.strip()
	    
            if 'Wavelength' in setting:
                wl=setting.split()[2]

            if 'Detector:' in setting:
                det0 = setting.split()[2].strip(',')
                if 'pilatus' in det0.lower(): det0 = 'Pilatus'
                det1 = setting.split()[3].strip(',')
                det = det0 + det1
                if det in ['Pilatus6M', 'Pilatus36M']: det = 'Pilatus6M'
        return distance, psx, psy, wl, bx, by, det
       
