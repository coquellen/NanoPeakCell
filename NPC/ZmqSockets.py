import zmq
import datetime


class ZMQPush(object):

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
        pusher = context.socket(zmq.PUSH)
        for opt in self.opts:
            pusher.setsockopt(opt, 1)
        pusher.bind("tcp://{0}:{1}".format(self.host, self.port))

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

    def close(self):
        """
        close and disable stream
        """
        if self.verbose:
            print("Closing connection of Push")
        return self.pusher.close()

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

    def receive(self, msg):
        """
        receive and return zmq frames if available
        """
        msg = self.puller.recv_json(flags=self.flags)
        if self.verbose:
            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print("[%s] received zmq json msg" % t)
        return msg


class EigerZMQStream(ZMQPull):

    def __init__(self, host, port=9999, verbose=False):
        """
            create stream listener object
            """
        ZMQPull.__init__(self, host, port)

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
