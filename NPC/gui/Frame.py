import fabio
import h5py
import os
import glob
from PyQt4 import QtCore, QtGui
import cPickle

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



    def openframe(self, fn, path='/data', index=None):
        self.filename = fn
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
        #print fn, path, index
        #try:
        print self.h5_dic[fn]
        for dataset in  self.h5_dic[fn]:
                if path == dataset[0]:
                    if index is None:
                      data = self.h5[path][:]
                      return None,data
                    else:
                        data = self.h5[path][index,::]
                        return None, data
        #except:
        #    return None, None

    def openimg(self,fn):
        img = fabio.open(fn)
        return img.header, img.data

    def openpickle(self,fn):
        try:
            #from libtbx import easy_pickle
            from scipy import ndimage

        except ImportError:
            print "Sorry, "
            return
        img = load_pickle(self.filename)

        # This code snippet helps to remove the border of each tile of the CSPAD (lots of overload)
        #
        #data = img['DATA'].as_numpy_array()
        #mask = np.where(data > 0, 0, 1)
        #s = ndimage.generate_binary_structure(2, 1)
        #self.dset = data*np.logical_not(ndimage.binary_dilation(mask, structure =s ))
        data = img['DATA'].as_numpy_array()
        return None, data



    def getImages(self):
        path = QtGui.QFileDialog.getExistingDirectory(
                       self.parent,
                       "Select a folder",
                       '/Users/nico/PycharmProjects/npg_qt')

        if path:
            self.tree.clear()
            os.chdir(path)
            self.run()

    def run(self):
            files = []
            for f in self.types:
                files.extend(glob.glob('*.%s' % f))

            masters = [f for f in files if 'master.h5' in f]
            for master in sorted(masters):
                item = QtGui.QTreeWidgetItem(self.tree)
                item.setText(0, master)
                files.remove(master)
                root = master.strip('master.h5')
                datas = [f for f in files if root in f]

                for data in sorted(datas):
                    self.filename = data
                    self.h5_dic[self.filename] =[]
                    with h5py.File(data, 'r') as f:

                        f.visititems(self.visitor_func)
                    self.construct_tree(data, item)
                    files.remove(data)

            for f in files:
                if not f.endswith('.h5'):
                    item = QtGui.QTreeWidgetItem(self.tree)
                    item.setText(0, f)
                    item.setText(1, "1")
                else:
                    with h5py.File(f, 'r') as h5:
                        self.filename = f
                        self.h5_dic[self.filename] =[]
                        h5.visititems(self.visitor_func)
                    self.construct_tree(f, self.tree)

    def append_object(self,obj):
        if os.path.isfile(obj):
            self.append_file(obj)
        elif os.path.isdir(obj):
            self.tree.clear()
            os.chdir(obj)
            self.run()


    def append_file(self, fn):
        filename, file_extension = os.path.splitext(fn)

        if file_extension.strip('.') in self.types:
            self.add_tree(fn)

    def add_tree(self,f):
        if not f.endswith('.h5'):
                    item = QtGui.QTreeWidgetItem(self.tree)
                    item.setText(0, f)
                    item.setText(1, "1")
        else:
            with h5py.File(f, 'r') as h5:
                self.filename = f
                self.h5_dic[self.filename] =[]
                h5.visititems(self.visitor_func)
            self.construct_tree(f, self.tree)


    def construct_tree(self, f, parent):
        #try:

            #if len(self.h5_dic[f]) == 1:

            item = QtGui.QTreeWidgetItem(parent)
            item.setText(0,f)
            if len(self.h5_dic[f]) == 1:
            #for dataset in self.h5_dic[f]:
                path , shape = self.h5_dic[f][0]
                if shape[0] == 1:
                    item.setText(1,"1")
                else:
                    item.setText(1, str(shape[0]))
                    for i in range(min(100,shape[0])):
                        item1 = QtGui.QTreeWidgetItem(item)
                        item1.setText(0, '%s %8i'%(path,i))
            else:
                count = 0
                for dataset in self.h5_dic[f]:
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






       #except KeyError:
       #     print("Sorry - No suitable dataset found in %s" %f)

    def visitor_func(self, name, node):

            if isinstance(node, h5py.Dataset):
                if len(node.shape) == 2 and node.size > 512*512:
                    t = (1, node.shape[0], node.shape[1])
                    #try: self.h5_dic[self.filename].append((node.name, t))
                    #except KeyError: self.h5_dic[self.filename] = [(node.name, t)]
                    self.h5_dic[self.filename].append((node.name, t))
                if len(node.shape) == 3 and node.shape[1] * node.shape[2] > 512*512:
                    #print self.filename, node.name, node.shape
                    #try: self.h5_dic[self.filename].append((node.name, node.shape))
                    #except KeyError: self.h5_dic[self.filename] = [(node.name, node.shape)]
                    #self.h5_dic[self.filename] = (node.name, node.shape)
                    self.h5_dic[self.filename].append((node.name, node.shape))


            else:
                pass








