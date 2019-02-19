import h5py
import os
import glob
try:
    from PyQt5 import QtGui
except:
    from PyQt4 import QtGui

try:
    import cPickle
except ImportError:
    pass
from NPC.utils import Log, parseHits


class TreeFactory(object):

    def __init__(self, tree):
        self.h5_fn = None
        self.h5 = None
        self.tree = tree
        self.filename = None
        self.types = ( 'edf',
                       'h5',
                       'cbf',
                       'img',
                       'sfrm',
                       'dm3',
                       'xml',
                       'kccd',
                       'msk',
                       'spr',
                       'tif',
                       'mccd',
                       'mar3450',
                       'pickle',
                       )
        self.h5_dic = {}
        self.filenames_dic = {}
        self.hits = None

    def run_hits(self, hits, clear=True):
        if clear:self.tree.clear()
        for f in hits.keys():

            self.addItem(f,self.tree)

    def run(self, path):
            self.hits = None
            files = []
            for f in self.types:
                files.extend(glob.glob(os.path.join(path,'*.%s' % f)))
            # TODO: Do not perform visitor_func for every data file !! - Seems OK (Could be done in the background by a Thread)
            # TODO: extract metadata from master
            # ID30a3 :
            # h5['/entry/instrument/beam/incident_wavelength'][()]
            # In [22]: h5['/entry/instrument/detector/description'][()]
            # Out[22]: 'Dectris Eiger 4M'
            # h5['/entry/instrument/detector/beam_center_x'][()]
            # h5['/entry/instrument/detector/detector_distance'][()] (meter)
            # TODO: Remove paths from tree name - Done
            # TODO:
            self.buildTree(files)

    def buildTree(self, files):
            masters = [f for f in files if 'master.h5' in f]
            for master in sorted(masters):
                master_item = self.addItem(master, self.tree,txt='')
                files.remove(master)
                root = master.strip('master.h5')
                datas = [f for f in files if root in f]

                for data in sorted(datas):
                    self.addItem(data, master_item)
                    files.remove(data)
            for f in files:
                self.addItem(f, self.tree)

    def append_object(self,obj):
        if os.path.isfile(obj):
            self.append_file(obj)
        elif os.path.isdir(obj):
            print("dir")
            self.hits= None
            self.tree.clear()
            self.run(str(obj))

    def append_file(self, fn):
        filename, file_extension = os.path.splitext(fn)
        if file_extension.strip('.') in self.types:
            self.hits = None
            self.addItem(fn, self.tree)
        if file_extension == '.txt':
            Log("Will load hits from list %s" % fn)
            self.hits = parseHits(fn)
            self.run_hits(self.hits)

    def restoreTree(self,dic):
        # This step is necessary to obtain str and not QString...
        newd = {}
        for k, v in dic.items():
            newd[str(k)] = str(v)
        ###
        self.buildTree(newd.values())
        self.filenames_dic = newd

    def addItem(self,f, parent,txt='tba'):
        path, fn = os.path.split(os.path.abspath(f))
        s = os.path.join(os.path.basename(path), fn)
        self.filenames_dic[s] = f
        item = QtGui.QTreeWidgetItem(parent)
        item.setText(0, s)
        if not f.endswith('.h5'):
            item.setText(1, "1")
        else:
            self.h5_dic[f] = []
            item.setText(1, txt)

        return item

    def construct_tree_h5(self, fn, item):
        self.filename = self.filenames_dic[fn]
        with h5py.File(self.filename, 'r') as h5:
            self.visitor_func(h5)
        if self.hits is None:
            if len(self.h5_dic[self.filename]) == 1:
                path, shape = self.h5_dic[self.filename][0]
                if shape[0] == 1:
                    item.setText(1,"1")
                    #print path, shape, self.filename
                    #Here emit a signal to display the file
                else:
                    item.setText(1, str(shape[0]))
                    for i in range(shape[0]):
                        item1 = QtGui.QTreeWidgetItem(item)
                        item1.setText(0, '%s %8i'%(path,i))
            else:
                count = 0
                for dataset in self.h5_dic[self.filename]:
                    path, shape = dataset
                    item1 = QtGui.QTreeWidgetItem(item)
                    item1.setText(0, path)
                    if shape[0] == 1:
                        item1.setText(1,  "1")
                    else:
                        item1.setText(1, str(shape[0]))
                        for i in range(min(100,shape[0])):
                            item2 = QtGui.QTreeWidgetItem(item1)
                            item2.setText(0, '%s %8i' % (path,i))
                        count += shape[0]
                    item.setText(1, str(count))
        else:
            hits = self.hits[self.filename]
            if isinstance(hits, int):
                item.setText(1, "1")
            else:
                path, shape = self.h5_dic[self.filename][0]
                for hit in hits:
                    item1 = QtGui.QTreeWidgetItem(item)
                    item1.setText(0, "%s %8s"%(path,hit))
                item.setText(1,str(len(hits)))

    def visitor_func(self, h5):
            for key in h5.keys():
                node = h5[key]
                if isinstance(node, h5py.Dataset):
                    if len(node.shape) == 2 and node.size > 512*512:
                        t = (1, node.shape[0], node.shape[1])
                        self.h5_dic[self.filename].append((node.name, t))
                    if len(node.shape) == 3 and node.shape[1] * node.shape[2] > 512*512:
                        self.h5_dic[self.filename].append((node.name, node.shape))
                else:
                    self.visitor_func(node)







