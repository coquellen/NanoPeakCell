# NanoPeakCell
==================

NanoPeakCell (NPC) is a python-software intended to pre-process your serial crystallography raw-data into ready-to-be-inedexed images with CrystFEL, cctbx.xfel and nXDS.
NPC is able to process data recorded at SACLA and LCLS XFELS, as well as data recorded at any synchrotron beamline.
A graphical interface is deployed to visualize your raw and pre-processed data.

Main features of NPC:
---------------------
Hit Finding based on a user-defined threshold.
Background subtraction performed on a per-frame basis (using pyFAI azimuthal integration)
Bragg peak localisation (sub-pixel refinement)
Conversion into the appropriate format for further data processing:
h5 --> crystFEL
pickle --> cctbx.xfel / cppxfel
cbf --> nXDS  

NPC dependencies:
-----------------
*numpy (>1.7)
*scipy
*h5py (and therefore hdf5)
*pyFAI  https://github.com/kif/pyFAI
*fabio  https://github.com/kif/fabio
cctbx.xfel (to save in the appropriate pickle format)

Gui dependencies:
-----------------
*PyQt4 (and hence Qt4)
*pyqtgraph


Extra dependencies:
-------------------
NPC is multiprocessed via the multiprocess module of python, or via mpi4py (to be run on multiple nodes on large clusters)
If you want to enable this feature, you will need some MPI library (Open-MP or MPICH) and mpi4py.

Installation:
-------------

Installation on MacOSX

I would recommend to use MacPorts. Please follow these instructions to install MacPorts: https://www.macports.org/install.php
And then run this command:
::
sudo port install py27-npc

If you want to be able to access mpi parallelization of NPC, a variant exists:
::
sudo port install py27-npc +mpi



Extra Notes:
-------------
If you intend to work with an Eiger detector; please compile this extra library 
https://github.com/dectris/HDF5Plugin

and move it to /opt/local/lib (for installation with MacPorts)


