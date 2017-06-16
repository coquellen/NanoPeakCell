import fabio
import h5py
import os
import glob
from PyQt4 import QtCore, QtGui
try:
    import cPickle
except ImportError:
    pass


from NPC.utils import Log, parseHits

def load_pickle(file_name, faster_but_using_more_memory=True):
  """
  Wraps cPickle.load.

  Parameters
  ----------
  file_name : str
  faster_but_using_more_memory : bool, optional
      Optionally read the entirety of a file into memory before converting it
      into a python object.

  Returns
  -------
  object
  """
  if (faster_but_using_more_memory):
    return cPickle.loads(open(file_name, "rb").read())
  return cPickle.load(open(file_name, "rb"))


class ConstructingTree(QtCore.QThread):

    def __init__(self, tree):
        QtCore.QThread.__init__(self, tree)
        self.tree = tree


class ImageFactory(object):

    def __init__(self, tree, parent):
        self.h5_fn = None
        self.h5 = None
        self.tree = tree
        self.parent = parent
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
        self.filename = None
        self.h5_dic = {}
        self.filenames_dic = {}
        self.hits = None

    def openframe(self, fn, path='/data', index=None):
        ext = os.path.splitext(fn)[1]
        if 'h5' in ext:
            return self.openh5(fn,index,path)
        elif 'pickle' in ext:
            return self.openpickle(fn)
        else:
            return self.openimg(fn)

    def openh5(self,fn, index=None, path='/data'):
        if fn != self.h5_fn:
            self.h5_fn = fn
            if self.h5 is not None: self.h5.close()
            self.h5 = h5py.File(fn)
        for dataset in self.h5_dic[fn]:
                if path == dataset[0]:
                    if index is None:
                      return None,self.h5[path][:].T
                    else:
                        return None, self.h5[path][index,::].T

    def openimg(self,fn):
        img = fabio.open(fn)
        return img.header, img.data.T

    def openpickle(self,fn):

        img = load_pickle(self.filename)
        # This code snippet helps to remove the border of each tile of the CSPAD (lots of overload)
        #
        #data = img['DATA'].as_numpy_array()
        #mask = np.where(data > 0, 0, 1)
        #s = ndimage.generate_binary_structure(2, 1)
        #self.dset = data*np.logical_not(ndimage.binary_dilation(mask, structure =s ))
        data = img['DATA'].as_numpy_array()
        return None, data.T

    def getImages(self):
        path = QtGui.QFileDialog.getExistingDirectory(
                       self.parent,
                       "Select a folder",
                       self.parent.cwd,
            QtGui.QFileDialog.DontUseNativeDialog | QtGui.QFileDialog.ShowDirsOnly)
        if path:
            self.parent.cwd=path
            self.tree.clear()
            self.run(str(path))

    def run_hits(self, hits):
        self.tree.clear()
        for f in hits.keys():
            if not f.endswith('.h5'):
                path, fn = os.path.split(os.path.abspath(f))
                s = os.path.join(os.path.basename(path), fn)
                self.filenames_dic[s] = f
                item = QtGui.QTreeWidgetItem(self.tree)
                item.setText(0, s)
                item.setText(1, "1")
            else:
                path, fn = os.path.split(os.path.abspath(f))
                s = os.path.join(os.path.basename(path), fn)
                self.filenames_dic[s] = f
                self.h5_dic[f] = []
                self.filename = f
                self.construct_tree(s, self.tree)


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

            masters = [f for f in files if 'master.h5' in f]
            for master in sorted(masters):
                item = QtGui.QTreeWidgetItem(self.tree)
                path, fn = os.path.split(os.path.abspath(master))
                s = os.path.join(os.path.basename(path), fn)
                self.filenames_dic[s] = master
                item.setText(0, s)
                files.remove(master)
                root = master.strip('master.h5')
                datas = [f for f in files if root in f]

                for data in sorted(datas):
                    self.filename = data
                    self.h5_dic[self.filename] = []
                    path, fn = os.path.split(self.filename)
                    s = os.path.join(os.path.basename(path), fn)
                    self.filenames_dic[s] = self.filename
                    self.construct_tree(s, item)
                    files.remove(data)

            for f in files:
                if not f.endswith('.h5'):
                    path, fn = os.path.split(os.path.abspath(f))
                    s = os.path.join(os.path.basename(path), fn)
                    self.filenames_dic[s] = f
                    item = QtGui.QTreeWidgetItem(self.tree)
                    item.setText(0, s)
                    item.setText(1, "1")
                else:
                    path, fn = os.path.split(os.path.abspath(f))
                    s = os.path.join(os.path.basename(path), fn)
                    self.filenames_dic[s] = f
                    self.h5_dic[f] = []
                    self.filename = f
                    self.construct_tree(s, self.tree)

    def append_object(self,obj):
        #print obj
        #obj = os.path.basename(obj)
        #print(obj)
        if os.path.isfile(obj):
            print('AAhhh0')
            self.append_file(obj)
        elif os.path.isdir(obj):
            print("dir")
            self.tree.clear()
            self.run(str(obj))


    def append_file(self, fn):
        print(fn)
        filename, file_extension = os.path.splitext(fn)
        if file_extension.strip('.') in self.types:
            self.add_tree(fn)
        if file_extension == '.txt':
            Log("Will load hits from list %s"%fn)
            self.hits = parseHits(fn)
            self.run_hits(self.hits)

    def add_tree(self,f):
        if not f.endswith('.h5'):
            path, fn = os.path.split(os.path.abspath(f))
            s = os.path.join(os.path.basename(path), fn)
            self.filenames_dic[s] = f
            item = QtGui.QTreeWidgetItem(self.tree)
            item.setText(0, s)
            item.setText(1, "1")
        else:
            path, fn = os.path.split(os.path.abspath(f))
            s = os.path.join(os.path.basename(path), fn)
            self.filenames_dic[s] = f
            self.h5_dic[f] = []
            self.filename = f
            self.construct_tree(s, self.tree)

    def construct_tree(self, f, parent):

            item = QtGui.QTreeWidgetItem(parent)
            item.setText(0,f)
            item.setText(1,'tba')

    def construct_tree_h5(self, fn, item):

        self.filename = self.filenames_dic[fn]
        with h5py.File(self.filename, 'r') as h5:
            h5.visititems(self.visitor_func)

        if self.hits is None:
            if len(self.h5_dic[self.filename]) == 1:
                path, shape = self.h5_dic[self.filename][0]
                if shape[0] == 1:
                    item.setText(1,"1")
                else:
                    item.setText(1, str(shape[0]))
                    for i in range(shape[0]):
                        item1 = QtGui.QTreeWidgetItem(item)
                        item1.setText(0, '%s %8i'%(path,i))
            else:
                count = 0
                for dataset in self.h5_dic[self.filename]:
                    path , shape = dataset
                    item1 = QtGui.QTreeWidgetItem(item)
                    item1.setText(0,path)
                    if shape[0] == 1:
                        item1.setText(1,"1")
                    else:
                        item1.setText(1, str(shape[0]))
                        for i in range(min(100,shape[0])):
                            item2 = QtGui.QTreeWidgetItem(item1)
                            item2.setText(0, '%s %8i'%(path,i))
                        count += shape[0]
                    item.setText(1, str(count))

        else:
            hits = self.hits[self.filename]
            path, shape = self.h5_dic[self.filename][0]
            for hit in hits:
                item1 = QtGui.QTreeWidgetItem(item)
                item1.setText(0, "%s %8s"%(path,hit))
            item.setText(1,str(len(hits)))


    def visitor_func(self, name, node):

            if isinstance(node, h5py.Dataset):
                if len(node.shape) == 2 and node.size > 512*512:
                    t = (1, node.shape[0], node.shape[1])
                    self.h5_dic[self.filename].append((node.name, t))

                if len(node.shape) == 3 and node.shape[1] * node.shape[2] > 512*512:
                    self.h5_dic[self.filename].append((node.name, node.shape))

            else:
                pass








