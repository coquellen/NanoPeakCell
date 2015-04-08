#!/Library/Frameworks/Python.framework/Versions/Current/bin/python
import os
import fabio
import h5py
import numpy as np
import NPC.peakfind as pf

try:
    from wx.lib.pubsub import pub
except ImportError:
    from pubsub import pub

try:
    from xfel.cxi.cspad_ana.cspad_tbx import dpack
    from xfel.command_line.cxi_image2pickle import crop_image_pickle  # , evt_timestamp
    from libtbx import easy_pickle
    from scitbx.array_family import flex

    cctbx = True
except ImportError:
    cctbx = False


def HitFinder(options, Detector, AI, fname):
    hit = 0
    peaks = []
    peakslist = []

    try:
        img = fabio.open(fname)
    except:
        print 'Warning : problem while opening file %s, file skiped ' % fname
        return
    if img.data.shape == Detector.shape:

        # Apply the dark, flatfield and distortion correction (as specified by the user)
        #img.data = DataCorr.apply_correction(img.data, HFParams.DoDarkCorr, HFParams.DoFlatCorr, HFParams.DoDist)


        #BkgCorr with pyFAI Azimuthal Integrator
        if options['background_subtraction'] !=  'None':
            working = AI.ai.separate(img.data, npt_rad=1024, npt_azim=512, unit="2th_deg", percentile=50, mask=Detector.mask,
                                     restore_mask=False)[0]
        else:
            working = img.data

        #Remove beam stop area (i.e = 0)
        extend = 15
        working[options['beam_y'] - extend:options['beam_y'] + extend, options['beam_x'] - extend:options['beam_x'] + extend] = 0

        imgmax, imgmin, imgmed = np.max(working), np.min(working), np.median(working)

        peaks = np.where(working > float(options['threshold']))
        if len(peaks[0]) >= options['npixels']:
            hit = 1
            root = os.path.basename(fname)
            root, extension = os.path.splitext(root)

            if options['bragg_search']:
                peakslist = pf.local_maxima(working.astype(np.int32), 3, 3, options['bragg_threshold'])

            result_folder = options['output_directory']
            num = options['num']
            if 'edf' in options['output_formats']:
                OutputFileName = os.path.join(result_folder, 'EDF_%s'%num.zfill(3), "%s.edf" % root)
                edfout = fabio.edfimage.edfimage(data=working.astype(np.int32), header=img.header)
                edfout.write(OutputFileName)


            #Conversion to H5
            if 'hdf5' in options['output_formats']:

                OutputFileName = os.path.join(result_folder, 'HDF5_%s'%num.zfill(3), "%s.h5" % root)
                #OutputFileName =os.path.join(IO.procdir, "HDF5/%s.h5" %root)
                OutputFile = h5py.File(OutputFileName, 'w')
                #if Detector.name == 'Frelon':
                #   working[0:Detector.resolution[0],Detector.resolution[1]-20:Detector.resolution[1]-1]=0
                OutputFile.create_dataset("data", data=working.astype(np.int32))
                if options['bragg_search']:
                    OutputFile.create_dataset("processing/hitfinder/peakinfo", data=peakslist.astype(np.int8))

                OutputFile.close()

            #if conversion to Pickle
            if 'pickles' in options['output_formats']:
                pixels = flex.int(working.astype(np.int32))
                pixel_size = Detector.pixel_size
                data = dpack(data=pixels,
                             distance=XSetup.distance,
                             pixel_size=pixel_size,
                             wavelength=XSetup.wavelength,
                             beam_center_x=XSetup.beam_y * pixel_size,
                             beam_center_y=XSetup.beam_x * pixel_size,
                             ccd_image_saturation=Detector.overload,
                             saturated_value=Detector.overload)
                data = crop_image_pickle(data)
                OutputFileName = os.path.join(result_folder, 'PICKLES_%s'%num.zfill(3), "%s.pickle" % root)
                easy_pickle.dump(OutputFileName, data)

        else:
            working = 0


    else:
        print 'Warning : data shape problem for file %s, file skiped ' % fname
    # continue

    return [hit, imgmax, imgmin, imgmed, len(peakslist), fname, working]
    
