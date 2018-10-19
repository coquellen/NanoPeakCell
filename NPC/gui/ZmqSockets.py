import zmq
import datetime, time
from PyQt4.QtCore import QTimer
import lz4
import bitshuffle
import numpy as np
import json
import struct
import os


class ZmqTimerManager(object):
    def __init__(self):
        self.timers = []
        self.next_call = 0

    def add_timer(self, timer):
        self.timers.append(timer)

    def check(self):
        if time.time() > self.next_call:
            for timer in self.timers:
                timer.check()

    def get_next_interval(self):
        if time.time() >= self.next_call:
            call_times = []
            for timer in self.timers:
                call_times.append(timer.get_next_call())
            self.next_call = min(call_times)
            if self.next_call < time.time():
                return 0
            else:
                return (self.next_call - time.time()) * 1000
        else:
            return (self.next_call - time.time()) * 1000


class ZmqTimer(object):
    def __init__(self, interval, callback, *args):
        self.interval = interval
        self.callback = callback
        self.last_call = 0
        self.backend, self.workers_MP, self.client, self.request = args

        self.N = 0


    def check(self):
        if time.time() > (self.interval + self.last_call) and len(self.workers_MP) > 0:
            self.callback(self.backend, self.workers_MP[self.N % len(self.workers_MP)], self.client, self.request)
            #self.backend.send_multipart([self.workers_MP[self.N % len(self.workers_MP)], b"", "MaxProj-Client", b"", "MAXPROJ"])
            self.N += 1
            print self.workers_MP, len(self.workers_MP)
            if self.N % len(self.workers_MP) == 0: self.N = 0

            self.last_call = time.time()

    def get_next_call(self):
        return self.last_call + self.interval


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
    dummy class to decode zmq frames from EIGER ZMQ stream
    """
    def __init__(self, basename="eigerStream", path=".", ftype="", verbose=False, roi=False):

        self.basename = basename
        self.ftype = ftype
        self.path = path

        if not os.path.isdir(self.path):
            raise IOError("[ERR] path %s does not exist" %self.path)

        #if roi: self.roi = ROI(*roi,verbose=verbose)
        #else: self.roi = ROI(verbose=verbose)

        self._verbose = verbose
        if self._verbose:
            print("[OK] initialized %s FileWriter" %self.ftype)

    def decodeFrames(self, frames):
        """
        decode and proces EIGER ZMQ stream frames
        """
        try:
            header = json.loads(frames[0].bytes)
        except Exception as e:
            print(e)
        if header["htype"].startswith("dheader-"):
            data = self.__decodeHeader__(frames)
        elif header["htype"].startswith("dimage-"):
            data = self.__decodeImage__(frames)
        elif header["htype"].startswith("dseries_end"):
            data = self.__decodeEndOfSeries__(frames)
        else:
            print("[ERR] not an EIGER ZMQ message")
            return False
        return data

    def __decodeImage__(self, frames):
        """
        decode ZMQ image frames
        """
        if self._verbose:
            print("[*] decode image")

        header = json.loads(frames[0].bytes) # header dict
        frameID = header["frame"]
        seriesID = header["series"]
        info = json.loads(frames[1].bytes) # info dict

        if info["encoding"] == "lz4<": # TODO: soft code flag
            data = self.readLZ4(frames[2], info["shape"], info["type"])

        elif "bs" in info["encoding"]:
            data = self.readBSLZ4(frames[2], info["shape"], info["type"])

        else:
            raise IOError("[ERR] encoding %s is not implemented" %info["encoding"])

        return seriesID, frameID, data

    def __decodeEndOfSeries__(self, frames):
        header = json.loads(frames[0].bytes)
        return header["series"], -2, "End of series"

    def __decodeHeader__(self, frames):
        """
        decode and process ZMQ header frames
        """
        if self._verbose:
            print("[*] decode header")
        header = json.loads(frames[0].bytes)
        seriesID = header["series"]
        if header["header_detail"]:
            if self._verbose:
                print(header)
        if header["header_detail"] is not "none":
            if self._verbose:
                print("detector config")
                for key, value in json.loads(frames[1].bytes).iteritems():
                    print(key, value)
        #if header["header_detail"] == "all":
        #    if json.loads(frames[2].bytes)["htype"].startswith("dflatfield"):
        #        if self._verbose:
        #            print "writing flatfield"
        #    if json.loads(frames[4].bytes)["htype"].startswith("dpixelmask"):
        #        if self._verbose:
        #            print "writing pixel mask"
        #    if json.loads(frames[6].bytes)["htype"].startswith("dcountrate"):
        #        if self._verbose:
        #            print("writing LUT")
        #if len(frames) == 9:
        #    if self._verbose:
        #        print("[*] appendix: ", json.loads(frames[8].bytes))
        return seriesID , -1, "Header"

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
            print("[OK] unpacked {0} bytes of bs-lz4 data".format(len(imgData)))
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
            print("[OK] unpacked {0} bytes of lz4 data".format(len(imgData)))

        return np.reshape(np.fromstring(imgData, dtype=dtype), shape[::-1])
