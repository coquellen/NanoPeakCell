import zmq
import datetime
from PyQt4.QtCore import QTimer
import bitshuffle, lz4
import numpy as np
import json
import struct
import os
import time


class ZMQPush(object):
    def __init__(self, host, port, opts=[], flags=0, meth = 'tcp', verbose=False):
        """
        create a Default ZMQ Pull socket
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        self.meth = meth
        self.opts = opts
        self.flags = flags
        self.connect()  # starts listening

    def connect(self):
        """
        open ZMQ pull socket
        return receiver object
        """

        context = zmq.Context()
        pusher = context.socket(zmq.PUSH)
        for opt in self.opts:
            pusher.setsockopt(opt, 1)
        print("{0}://{1}:{2}".format(self.meth, self.host, self.port))
        pusher.bind("{0}://{1}:{2}".format(self.meth, self.host, self.port))

        self.pusher = pusher
        return self.pusher

    def send(self, msg):
        """
        receive and return zmq frames if available
        """

        self.pusher.send_json(msg, flags=self.flags)
        if self.verbose:
            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print("[%s] sent zmq json msg" % t)
        return


class ZMQPull(object):

    def __init__(self, host, port, opts=[], flags=0, verbose=False):
        """
        create a Default ZMQ Pull socket
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        self.opts = opts
        self.flags = flags
        self.connect()  # starts listening

    def connect(self):
        """
        open ZMQ pull socket
        return receiver object
        """

        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        for opt in self.opts:
            puller.setsockopt(opt, 1)
        puller.connect("tcp://{0}:{1}".format(self.host, self.port))

        self.puller = puller
        return self.puller

    def receive(self):
        """
        receive and return zmq frames if available
        """
        msg = self.puller.recv_json(flags=zmq.NOBLOCK)
        if self.verbose:
            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print("[%s] received zmq json msg" % t)
        return msg

    def close(self):
        """
        close and disable stream
        """
        if self.verbose:
            print("Closing connection")
        return self.puller.close()


class ZMQPullBind(object):

        def __init__(self, host, port, opts=[], flags=0, verbose=False):
            """
            create a Default ZMQ Pull socket
            """
            self.host = host
            self.port = port
            self.verbose = verbose
            self.opts = opts
            self.flags = flags
            self.connect()  # starts listening

        def connect(self):
            """
            open ZMQ pull socket
            return receiver object
            """

            context = zmq.Context()
            puller = context.socket(zmq.PULL)
            for opt in self.opts:
                puller.setsockopt(opt, 1)
            print "Puller: tcp://{0}:{1}".format(self.host, self.port)
            puller.bind("tcp://{0}:{1}".format(self.host, self.port))

            self.puller = puller
            return self.puller

        def receive(self):
            """
            receive and return zmq frames if available
            """
            msg = self.puller.recv(flags=zmq.NOBLOCK)
            if self.verbose:
                t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                print("[%s] received zmq json msg" % t)
            return msg

        def close(self):
            """
            close and disable stream
            """
            if self.verbose:
                print("Closing connection")
            return self.puller.close()


class ZMQPushMulti(ZMQPush):

    def __init__(self,  host, port, opts=[], flags=0, verbose=False):
        super(ZMQPushMulti, self).__init__( host, port, opts=[], flags=0, verbose=False)

    def connect(self):
        context = zmq.Context()
        pusher = context.socket(zmq.PUSH)
        for opt in self.opts:
            pusher.setsockopt(opt, 1)
        print("{0}://{1}:{2}".format(self.meth, self.host, self.port))
        pusher.connect("{0}://{1}:{2}".format(self.meth, self.host, self.port))

        self.pusher = pusher
        return self.pusher

    def send(self, msg):
        """
        receive and return zmq frames if available
        """

        self.pusher.send_json(msg, flags=self.flags)
        if self.verbose:
            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print("[%s] sent zmq json msg" % t)
        return


class EigerZMQStream(ZMQPull):

    def __init__(self, host, port=9999, verbose=False):
        """
            create stream listener object
            """
        super(EigerZMQStream, self).__init__(host, port)
        self.receiver = self.puller

    def receive(self):
        """
        receive and return zmq frames if available
        """
        if self.receiver.poll(100):  # check if message available
            frames = self.receiver.recv_multipart(copy=False)
            if self.verbose:
                t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                print("[%s] received zmq frames with length %d" % (t, len(frames)))
            return frames


class NPGPull(ZMQPull):

    def __init__(self, host, port, imgModel, table, opts, flags):
        ZMQPull.__init__(self, host, port, opts=[], flags=flags)
        self.socketTimer = QTimer()
        self.socketTimer.timeout.connect(self.receive)
        self.imgModel = imgModel
        self.table = table

    def start(self):
        self.connect()
        self.socketTimer.start(100)

    def stop(self):
        self.close()
        self.socketTimer.stop()

    def receive(self):

        try:
            data = self.puller.recv_json(flags=zmq.NOBLOCK)
            fn = str(data['fn'].strip())
            path = str(data['path'])
            index = int(data['index'])
            total = int(data['total'])
            N = int(data['processed'])
            hit = int(data['hit'])
            self.imgModel.updateData(fn, path, int(index))
            self.table.progress((total, N, hit))
            return
        except zmq.error.Again:
            return





class EigerStreamDecoder():
    """
    Class to decode zmq frames from EIGER ZMQ stream
    """
    def __init__(self, verbose=False, roi=False):

        #self.basename = basename
        #self.ftype = ftype
        #self.path = path

        #if not os.path.isdir(self.path):
        #    raise IOError("[ERR] path %s does not exist" %self.path)

        #if roi: self.roi = ROI(*roi,verbose=verbose)
        #else: self.roi = ROI(verbose=verbose)

        self._verbose = verbose
        #if self._verbose:
        #    print "[OK] initialized %s FileWriter" %self.ftype

    def decodeFrames(self, frames):
        """
        decode and proces EIGER ZMQ stream frames
        """
        try:
            header = json.loads(frames[0].bytes)
        except Exception as e:
            print e
            return False
        if header["htype"].startswith("dheader-"):
            return self.__decodeHeader__(frames)
        elif header["htype"].startswith("dimage-"):
            return self.__decodeImage__(frames)
        elif header["htype"].startswith("dseries_end"):
            return self.__decodeEndOfSeries__(frames)
        else:
            print "[ERR] not an EIGER ZMQ message"
            return 0, -3, False


    def __decodeImage__(self, frames):
        """
        decode ZMQ image frames
        """
        if self._verbose:
            print "[*] decode image"

        header = json.loads(frames[0].bytes) # header dict
        frameID = header["frame"]
        seriesID = header["series"]

        info = json.loads(frames[1].bytes) # info dict

        if info["encoding"] == "lz4<": # TODO: soft code flag
            data = self.readLZ4(frames[2], info["shape"], info["type"])
        elif "bs" in info["encoding"]:
            print info["encoding"]
            data = self.readBSLZ4(frames[2], info["shape"], info["type"])
        else:
            raise IOError("[ERR] encoding %s is not implemented" %info["encoding"])

        return seriesID, frameID, data

    def __decodeEndOfSeries__(self, frames):
        if self._verbose:
            print "[OK] received end of series ", json.loads(frames[0].bytes)

        return 0, -2, "End of series"

    def __decodeHeader__(self, frames):
        """
        decode and process ZMQ header frames
        """
        if self._verbose:
            print "[*] decode header"
        header = json.loads(frames[0].bytes)
        if header["header_detail"]:
            if self._verbose:
                print header
        if header["header_detail"] is not "none":
            if self._verbose:
                print "detector config"
                for key, value in json.loads(frames[1].bytes).iteritems():
                    print key, value
        if header["header_detail"] == "all":
            if json.loads(frames[2].bytes)["htype"].startswith("dflatfield"):
                if self._verbose:
                    print "writing flatfield"
            if json.loads(frames[4].bytes)["htype"].startswith("dpixelmask"):
                if self._verbose:
                    print "writing pixel mask"
            if json.loads(frames[6].bytes)["htype"].startswith("dcountrate"):
                if self._verbose:
                    print "writing LUT"
        if len(frames) == 9:
            if self._verbose:
                print "[*] appendix: ", json.loads(frames[8].bytes)

        return 0, -1, "Header"

    def readBSLZ4(self, frame, shape, dtype):
        """
        unpack bitshuffle-lz4 compressed frame and return np array image data
        frame: zmq data blob frame
        shape: image shape
        dtype: image data type
        """

        data = frame.bytes
        blob = np.fromstring(data[12:], dtype=np.uint8)
        dtype = np.dtype(dtype)
        # blocksize is big endian uint32 starting at byte 8, divided by element size
        blocksize = np.ndarray(shape=(), dtype=">u4", buffer=data[8:12])/dtype.itemsize
        imgData = bitshuffle.decompress_lz4(blob, shape[::-1], dtype, blocksize)
        if self._verbose:
            print "[OK] unpacked {0} bytes of bs-lz4 data".format(len(imgData))
        return imgData

    def readLZ4(self, frame, shape, dtype):
        """
        unpack lz4 compressed frame and return np array image data
        frame: zmq data blob frame
        shape: image shape
        dtype:image data type
        """
        dtype = np.dtype(dtype)
        dataSize = dtype.itemsize*shape[0]*shape[1] # bytes * image size

        imgData = lz4.loads(struct.pack('<I', dataSize) + frame.bytes)
        if self._verbose:
            print "[OK] unpacked {0} bytes of lz4 data".format(len(imgData))

        return np.reshape(np.fromstring(imgData, dtype=dtype), shape[::-1])






#from multiprocessing import Process

# class NPGLiveStream(Process):
#
#     def __init__(self, Eigerhost, host, HFParams, rank, size, shape, debug):
#         super(NPGLiveStream, self).__init__()
#         self.host = host
#         self.debug = debug
#         self.HFParams = HFParams
#         self.threshold = HFParams.threshold
#         self.npixels = HFParams.npixels
#         self.x1, self.y1, self.x2, self.y2 = HFParams.roi
#         self.mask = HFParams.mask
#         self.rank = rank
#         self.size = size
#         self.data = np.zeros((5, shape[0], shape[1]))
#         self.maxproj = 0
#
#         self.NProcessed = 0
#         self.Nhits = 0
#
#         self.eigerStream = EigerZMQStream(Eigerhost)
#         self.streamDecoder = FileWriter()
#         #self.statsSender = ZMQPushMulti(host=self.host, port=5556)
#         context = zmq.Context()
#         # recieve work
#         #consumer_receiver = context.socket(zmq.PULL)
#         #consumer_receiver.connect("tcp://127.0.0.1:5557")
#         # send work
#         self.socket = context.socket(zmq.REQ)
#         self.socket.connect("tcp://127.0.0.1:5558")
#
#     def run(self):
#         import h5py
#         i = 0
#         h5 = h5py.File('/Users/coquelleni/PycharmProjects/NanoPeakCell_0.3.2/NPC_DATA/tcache_2_358_data_000020.h5','r')
#         while True:
#             if not self.debug:
#                 frames = self.eigerStream.receive()
#                 if frames:
#                     data = self.streamDecoder.decodeFrames(frames)
#                     if hasattr(data, 'shape'):
#                         self.process(data)
#             else:
#                 data = h5['/entry/data/data/'][i%100,::]
#                 self.process(data)
#                 i += 1
#
#
#                     #self.sender.send(msg)
#
#     def process(self, data):
#         #data = data[self.y1:self.y2, self.x1:self.x2]
#         #data *= self.mask.astype(data.dtype)
#         #self.maxproj = np.amax(self.data,axis=0)
#         self.NProcessed += 1
#         if data[data > self.threshold].size > self.npixels:
#             self.Nhits += 1
#             #self.req.send(data)
#
#         if self.NProcessed % 10 == 0:
#             d = {}
#             d["processed"] = self.NProcessed
#             d["hits"] = self.Nhits
#             print("Sending")
#             self.socket.send_json(d)
#             reply = self.socket.recv()
#             #print 'client: ack'
#             self.NProcessed = 0
#             self.Nhits = 0
#
#
#
