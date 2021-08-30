from pyqtgraph import ptime
import zmq
import time
import numpy as np
import h5py
import requests
import json
from NPC.utils import Log
from NPC.gui.ZmqSockets import ZmqTimerManager, ZmqTimer
import os
from NPC.dozor import dozor
import fabio


class NPC_Zmq(object):

    def __init__(self, wrk_num, ip_address_viewer):
        self.context0 = zmq.Context()

        # The connection of the streanReceiver will be done in a subcllass
        self.streamReceiver = self.context0.socket(zmq.PULL)

        # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
        self.results_sender = self.context0.socket(zmq.PUSH)
        self.results_sender.connect("tcp://%s:5558" % ip_address_viewer)

        # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
        self.control_receiver = self.context0.socket(zmq.SUB)
        self.control_receiver.connect("tcp://%s:5559" % ip_address_viewer)
        #Subscribe to all messages
        self.control_receiver.setsockopt(zmq.SUBSCRIBE, "")

        # Set up a channel to send messages to the load balancer (including images)
        #
        self.backend = zmq.Context().socket(zmq.DEALER)
        self.backend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
        self.backend.connect("tcp://%s:5571" % ip_address_viewer)

        self.MPbackend = zmq.Context().socket(zmq.DEALER)
        self.MPbackend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
        self.MPbackend.connect("tcp://%s:5561" % ip_address_viewer)

    def send_start_to_backends(self):
        self.MPbackend.send(b"START")
        # send a start message to receive the parameters from the gui at startup...
        self.backend.send(b"START")

class NPC_Zmq_Eiger(NPC_Zmq):

    def __init__(self, wrk_num, HF, ip_address_viewer):
        super(NPC_Zmq_Eiger, self).__init__(wrk_num, ip_address_viewer)
        from NPC.gui.ZmqSockets import EigerStreamDecoder
        streamDecoder = EigerStreamDecoder()
        self.streamReceiver.connect("tcp://%s:9999" % HF.ip)
        if wrk_num == 0:
            Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" % HF.ip)

class NPC_Zmq_Pilatus(NPC_Zmq):

    def __init__(self, wrk_num, HF, ip_address_viewer):
        super(NPC_Zmq_Pilatus, self).__init__(wrk_num, ip_address_viewer)
        self.streamReceiver.connect("tcp://%s:9999" % ip_address_viewer)
        if wrk_num == 0:
            Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" % HF.ip)




def openMask(fn):
    h51 = h5py.File(fn, 'r')
    data = -1 * (h51['data'][:] - 1)
    h51.close()
    return data.astype(np.int32)

def cbf_ventilator(mxcube_dic):
    # Initialize a zeromq context
    context = zmq.Context()

    # Set up a channel to send work
    ventilator_send = context.socket(zmq.PUSH)
    ventilator_send.bind("tcp://*:9999")

    #Set up a channel to send data collection info
    # Give everything a second to spin up and connect
    time.sleep(1)
    Log("Ventilator sending mxcube_info")
    ventilator_send.send_json(mxcube_dic)

    # Send the numbers between 1 and 1 million as work messages
    num = mxcube_dic['image_first']
    while num <= mxcube_dic['number_images']:
        fn = mxcube_dic['template'].replace('????', str(num).zfill(4))
        work_message = {'filename': fn}
        if os.path.isfile(fn):
            ventilator_send.send_json(work_message)
            num += 1
            time.sleep(mxcube_dic['exposure'])


    #time.sleep(1)
    print("Ventilator Done")


def workerEiger(wrk_num, HF, ip_adress_viewer='localhost'):

    nplive_zmq = NPC_Zmq_Eiger(wrk_num, HF, ip_adress_viewer)
    nplive_zmq.send_start_to_backends()

    newParams = nplive_zmq.backend.recv_json()
    for key in newParams.keys():
        #if getattr(HF, key) is None:
        setattr(HF, key, newParams[key])
    if HF.maskFN is not None:
        import time
        time.sleep(wrk_num/2.)
        HF.mask = openMask(HF.maskFN)
    #

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(nplive_zmq.streamReceiver, zmq.POLLIN)
    poller.register(nplive_zmq.control_receiver, zmq.POLLIN)
    poller.register(nplive_zmq.backend, zmq.POLLIN)
    poller.register(nplive_zmq.MPbackend, zmq.POLLIN)

    # Loop and accept messages from both channels, acting accordingly
    Nprocessed = 0
    Nhits = 0
    total = 0
    p0 = ptime.time()
    data = None

    if HF.debug:
        MP = np.full(HF.shape, wrk_num, dtype=np.int32)
    else:
        MP = np.zeros(HF.shape, dtype=np.int32)

    data2SND = True
    hit_IDX = []
    nohit_IDX = []


    while True:

        socks = dict(poller.poll())
        # If the message comes from stream,
        if socks.get(nplive_zmq.streamReceiver) == zmq.POLLIN:

            #This should be coded in a function of a Worker_Zmq class object
            frames = nplive_zmq.streamReceiver.recv_multipart(copy=False)
            seriesID, frameID, data = nplive_zmq.streamDecoder.decodeFrames(frames)

            # the decodeFrames returns -1 for the header
            # and -2 for the end of series messages
            if frameID >= 0:

                if (HF.RADDAM and (frameID % HF.NShots) == 10) or not HF.RADDAM:
                    Nprocessed += 1
                    total += 1
                    if HF.mask is not None:
                        data = data * HF.mask
                    roi = data[HF.x1:HF.x2, HF.y1:HF.y2]

                    hit = data
                    if roi[roi > HF.threshold].size > HF.npixels:
                        Nhits += 1
                        hit = data
                        hit_IDX.append(frameID)
                        if HF.computeMP:
                            MP = np.maximum(MP, data)
                        if data2SND:
                            nplive_zmq.backend.send(b"READY")
                            data2SND = False
                    else:
                        nohit_IDX.append(frameID)

            elif frameID == -1:
                r = requests.get("http://%s/filewriter/api/1.3.0/config/name_pattern" % HF.ip)
                if r.status_code == 200:
                    name_pattern = r.json()["value"]
                    Log("--- Header message received ---")
                    Log("--- Eiger series started: %s ---" % name_pattern.replace('$id', str(seriesID)))
                    nplive_zmq.results_sender.send_json({"name_pattern": name_pattern, "series": seriesID})

            elif frameID == -2:
                r = requests.get("http://%s/stream/api/1.3.1/status/dropped" % HF.ip)
                # results_sender.send_json(stats)
                if r.status_code == 200:
                    dropped = r.json()["value"]
                    Log("--- End of series ---")
                    Log("--- Dropped %i images ---" % dropped)
                    nplive_zmq.results_sender.send_json({"End": dropped})
                    # backend.send(b"End of Series")

            elif frameID == -3:
                Log("Worker %i received a non ZMQ Eiger message... Weird...")

        # If the message came over the control channel, update parameters.
        if socks.get(nplive_zmq.control_receiver) == zmq.POLLIN:
            newParams = nplive_zmq.control_receiver.recv_json(zmq.NOBLOCK)

            if newParams.keys()[0] in ["STOP", "resetMP"]:
                key = newParams.keys()[0]
                if newParams[key] == "resetMP":
                    MP[::] = 0
                    if wrk_num == 0:
                        nplive_zmq.MPbackend.send(b"resetMP")
                        Log("Message received from Control Gui: Resetting MP")


                elif newParams[key] == "STOP":
                    if wrk_num == 0:
                        nplive_zmq.backend.send(b"STOP")
                        nplive_zmq.MPbackend.send(b"STOP")
                        Log("Message received from Control Gui: Exiting")
                    break

            else:
                for key in newParams.keys():
                    setattr(HF, key, newParams[key])
                    if wrk_num == 0:
                        Log("Message received from Control Gui: Setting %s to value %s"%(key,str(newParams[key])))

        if socks.get(nplive_zmq.backend) == zmq.POLLIN:
            _, address, _, request = nplive_zmq.backend.recv_multipart()
            if hasattr(data, 'shape'):
                    print("Sending data")
                    nplive_zmq.backend.send(address, flags=zmq.SNDMORE)
                    nplive_zmq.backend.send_json({'dtype': str(data.dtype), 'shape': data.shape}, flags=zmq.SNDMORE)
                    nplive_zmq.backend.send(hit, flags=0, copy=False, track=False)
                    data2SND = True

        if socks.get(nplive_zmq.MPbackend) == zmq.POLLIN:
            _, address, _, request = nplive_zmq.MPbackend.recv_multipart()
            nplive_zmq.MPbackend.send(address, flags=zmq.SNDMORE)
            nplive_zmq.MPbackend.send_json({'dtype': str(MP.dtype), 'shape': MP.shape}, flags=zmq.SNDMORE)
            nplive_zmq.MPbackend.send(MP, flags=0, copy=False, track=False)

        # If enough time elapsed... send stats via the result channel @ 5558 (PUSH socket)
        p1 = ptime.time()
        if p1 - p0 > 0.5:
            if Nprocessed > 0:
                stats = {'worker': wrk_num, 'processed': Nprocessed, 'hits': Nhits}
                nplive_zmq.results_sender.send_json(stats)
                Nprocessed = 0
                Nhits = 0
                p0 = p1

    nplive_zmq.backend.close()
    nplive_zmq.MPbackend.close()
    nplive_zmq.streamReceiver.close()
    nplive_zmq.results_sender.close()
    nplive_zmq.control_receiver.close()
    nplive_zmq.context0.term()
    Log("Worker %i exited properly" %wrk_num)


def workerPilatus(wrk_num, HF, ip_adress_viewer='localhost'):

    nplive_zmq = NPC_Zmq_Pilatus(wrk_num, HF, ip_adress_viewer)
    nplive_zmq.send_start_to_backends()

    # This is common to all workers and should be
    newParams = nplive_zmq.backend.recv_json()
    for key in newParams.keys():
        #if getattr(HF, key) is None:
        setattr(HF, key, newParams[key])
    if HF.maskFN is not None:
        import time
        time.sleep(wrk_num/2.)
        HF.mask = openMask(HF.maskFN)
    #

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(nplive_zmq.streamReceiver, zmq.POLLIN)
    poller.register(nplive_zmq.control_receiver, zmq.POLLIN)
    poller.register(nplive_zmq.backend, zmq.POLLIN)
    poller.register(nplive_zmq.MPbackend, zmq.POLLIN)

    Nprocessed = 0
    Nhits = 0
    total = 0
    p0 = ptime.time()
    data = None

    if HF.debug:
        MP = np.full(HF.shape, wrk_num, dtype=np.int32)
    else:
        MP = np.zeros(HF.shape, dtype=np.int32)

    data2SND = True
    hit_IDX = []
    nohit_IDX = []
    spots = []
    d = dozor.Dozor()
    dozor_READY = False

    while True:
        socks = dict(poller.poll())
        # If the message comes from ventilator
        if socks.get(nplive_zmq.streamReceiver) == zmq.POLLIN:
            #Log("Worker received a message from the ventilator")
            #This should be coded in a function of a Worker_Zmq class object
            fn = nplive_zmq.streamReceiver.recv_json()

            if len(fn.keys()) > 1:
                Log("Worker %i sending data collection info to load balancer" %wrk_num)
                nplive_zmq.backend.send(b"DATA COLLECTION START", flags=zmq.SNDMORE)
                nplive_zmq.backend.send_json(fn)

            else:
                if dozor_READY:
                    #Log("Worker %i processing filename %s" %(wrk_num, fn['filename']))
                    data = fabio.open(fn['filename']).data
                    dozor_data, spots = d.do_image(data.astype(np.uint16))
                    Nprocessed += 1
                    total += 1
                    if len(spots) > 0:
                        Nhits += 1
                        hit_IDX.append(fn['filename'])

                        #hit = data
                        #if data2SND:
                        #    nplive_zmq.backend.send(b"READY")
                        #    data2SND = False

                    else:
                        nohit_IDX.append(fn['filename'])

                    hit = data
                    if data2SND:
                        nplive_zmq.backend.send(b"READY")
                        data2SND = False

                    #Log("Worker %i processed image %s: %5i spots found" %(wrk_num, fn['filename'][-8:], len(spots)))
                else:
                    print("Worker %i dropping filename %s" %(wrk_num, fn['filename']))

        # If the message came over the control channel, update parameters.
        if socks.get(nplive_zmq.control_receiver) == zmq.POLLIN:
            newParams = nplive_zmq.control_receiver.recv_json(zmq.NOBLOCK)

            if newParams.keys()[0] in ["STOP", "resetMP"]:
                key = newParams.keys()[0]
                if newParams[key] == "resetMP":
                    MP[::] = 0
                    if wrk_num == 0:
                        nplive_zmq.MPbackend.send(b"resetMP")
                        Log("Message received from Control Gui: Resetting MP")


                elif newParams[key] == "STOP":
                    if wrk_num == 0:
                        nplive_zmq.backend.send(b"STOP")
                        nplive_zmq.MPbackend.send(b"STOP")
                        Log("Message received from Control Gui: Exiting")
                    break

            else:
                for key in newParams.keys():
                    setattr(HF, key, newParams[key])
                    if wrk_num == 0:
                        Log("Message received from Control Gui: Setting %s to value %s"%(key,str(newParams[key])))

        if socks.get(nplive_zmq.backend) == zmq.POLLIN:


            request = nplive_zmq.backend.recv_multipart()

            if request[0] == b"DATA COLLECTION START":
                mxcube_dic = json.loads(request[1])
                d.read_dozor_live(mxcube_dic)
                dozor_READY = True
            else:
                _, address, _, req = request

            if hasattr(data, 'shape'):
                    #print("Sending data")
                    x = []
                    y = []
                    #i = []
                    for spot in spots:
                        x.append(spot.x)
                        y.append(spot.y)
                        #i.append(spot.intensity)
                    nplive_zmq.backend.send(address, flags=zmq.SNDMORE)
                    nplive_zmq.backend.send_json({'dtype': str(data.dtype), 'shape': data.shape}, flags=zmq.SNDMORE)
                    nplive_zmq.backend.send_json({'x': x, 'y': y}, flags=zmq.SNDMORE)
                    nplive_zmq.backend.send(hit, flags=0, copy=False, track=False)
                    data2SND = True

        if socks.get(nplive_zmq.MPbackend) == zmq.POLLIN:
            Log("Sending info to MP Load Balancer")
            _, address, _, request = nplive_zmq.MPbackend.recv_multipart()
            nplive_zmq.MPbackend.send(address, flags=zmq.SNDMORE)
            nplive_zmq.MPbackend.send_json({'spots' : spots})
            spots = []
            #nplive_zmq.MPbackend.send_json({'dtype': str(MP.dtype), 'shape': MP.shape}, flags=zmq.SNDMORE)
            #nplive_zmq.MPbackend.send(MP, flags=0, copy=False, track=False)

        # If enough time elapsed... send stats via the result channel @ 5558 (PUSH socket)
        p1 = ptime.time()
        if p1 - p0 > 0.5:
            if Nprocessed > 0:
                stats = {'worker': wrk_num, 'processed': Nprocessed, 'hits': Nhits}
                nplive_zmq.results_sender.send_json(stats)
                Nprocessed = 0
                Nhits = 0
                p0 = p1

    nplive_zmq.backend.close()
    nplive_zmq.MPbackend.close()
    nplive_zmq.streamReceiver.close()
    nplive_zmq.results_sender.close()
    nplive_zmq.control_receiver.close()
    nplive_zmq.context0.term()
    Log("Worker %i exited properly" %wrk_num)



def _workerEiger(wrk_num, HF, ip_adress_viewer='localhost'):


    from NPC.gui.ZmqSockets import EigerStreamDecoder
    #This class has been generously provided by Sacha Grimm from Dectris, and slightly modified for our implementation
    streamDecoder = EigerStreamDecoder()

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The Eiger stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    # This will be different for cbfs
    if wrk_num == 0:
        Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)

    streamReceiver = context0.socket(zmq.PULL)
    streamReceiver.connect("tcp://%s:9999" % HF.ip)
    #

    # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
    results_sender = context0.socket(zmq.PUSH)
    results_sender.connect("tcp://%s:5558" % ip_adress_viewer)

    # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
    control_receiver = context0.socket(zmq.SUB)
    control_receiver.connect("tcp://%s:5559" % ip_adress_viewer)
    #Subscribe to all messages
    control_receiver.setsockopt(zmq.SUBSCRIBE, "")

    # Set up a channel to send messages to the load balancer (including images)
    #
    backend = zmq.Context().socket(zmq.DEALER)
    backend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
    backend.connect("tcp://localhost:5571")

    MPbackend = zmq.Context().socket(zmq.DEALER)
    MPbackend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
    MPbackend.connect("tcp://localhost:5561")

    MPbackend.send(b"START")
    # send a start message to receive the parameters from the gui at startup...
    backend.send(b"START")

    newParams = backend.recv_json()
    for key in newParams.keys():
        #if getattr(HF, key) is None:
        setattr(HF, key, newParams[key])
    if HF.maskFN is not None:
        import time
        time.sleep(wrk_num/2.)
        HF.mask = openMask(HF.maskFN)
    #

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(streamReceiver, zmq.POLLIN)
    poller.register(control_receiver, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)
    poller.register(MPbackend, zmq.POLLIN)

    # Loop and accept messages from both channels, acting accordingly
    Nprocessed = 0
    Nhits = 0
    total = 0
    p0 = ptime.time()
    data = None

    if HF.debug:
        MP = np.full(HF.shape, wrk_num, dtype=np.int32)
    else:
        MP = np.zeros(HF.shape, dtype=np.int32)

    data2SND = True
    hit_IDX = []
    nohit_IDX = []


    while True:

        socks = dict(poller.poll())
        # If the message comes from stream,
        if socks.get(streamReceiver) == zmq.POLLIN:

            #This should be coded in a function of a Worker_Zmq class object
            frames = streamReceiver.recv_multipart(copy=False)
            seriesID, frameID, data = streamDecoder.decodeFrames(frames)

            # the decodeFrames returns -1 for the header
            # and -2 for the end of series messages
            if frameID >= 0:

                if (HF.RADDAM and (frameID % HF.NShots) == 10) or not HF.RADDAM:
                    Nprocessed += 1
                    total += 1
                    if HF.mask is not None:
                        data = data * HF.mask
                    roi = data[HF.x1:HF.x2, HF.y1:HF.y2]

                    hit = data
                    if roi[roi > HF.threshold].size > HF.npixels:
                        Nhits += 1
                        hit = data
                        hit_IDX.append(frameID)
                        if HF.computeMP:
                            MP = np.maximum(MP, data)
                        if data2SND:
                            backend.send(b"READY")
                            data2SND = False
                    else:
                        nohit_IDX.append(frameID)

            elif frameID == -1:
                r = requests.get("http://%s/filewriter/api/1.3.0/config/name_pattern" % HF.ip)
                if r.status_code == 200:
                    name_pattern = r.json()["value"]
                    Log("--- Header message received ---")
                    Log("--- Eiger series started: %s ---" % name_pattern.replace('$id', str(seriesID)))
                    results_sender.send_json({"name_pattern": name_pattern, "series": seriesID})

            elif frameID == -2:
                r = requests.get("http://%s/stream/api/1.3.1/status/dropped" % HF.ip)
                # results_sender.send_json(stats)
                if r.status_code == 200:
                    dropped = r.json()["value"]
                    Log("--- End of series ---")
                    Log("--- Dropped %i images ---" % dropped)
                    results_sender.send_json({"End": dropped})
                    # backend.send(b"End of Series")

            elif frameID == -3:
                Log("Worker %i received a non ZMQ Eiger message... Weird...")

        # If the message came over the control channel, update parameters.
        if socks.get(control_receiver) == zmq.POLLIN:
            newParams = control_receiver.recv_json(zmq.NOBLOCK)

            if newParams.keys()[0] in ["STOP", "resetMP"]:
                key = newParams.keys()[0]
                if newParams[key] == "resetMP":
                    MP[::] = 0
                    if wrk_num == 0:
                        MPbackend.send(b"resetMP")
                        Log("Message received from Control Gui: Resetting MP")


                elif newParams[key] == "STOP":
                    if wrk_num == 0:
                        backend.send(b"STOP")
                        MPbackend.send(b"STOP")
                        Log("Message received from Control Gui: Exiting")
                    break

            else:
                for key in newParams.keys():
                    setattr(HF, key, newParams[key])
                    if wrk_num == 0:
                        Log("Message received from Control Gui: Setting %s to value %s"%(key,str(newParams[key])))

        if socks.get(backend) == zmq.POLLIN:
            _, address, _, request = backend.recv_multipart()
            if hasattr(data, 'shape'):
                    print("Sending data")
                    backend.send(address, flags=zmq.SNDMORE)
                    backend.send_json({'dtype': str(data.dtype), 'shape': data.shape}, flags=zmq.SNDMORE)
                    backend.send(hit, flags=0, copy=False, track=False)
                    data2SND = True

        if socks.get(MPbackend) == zmq.POLLIN:
            _, address, _, request = MPbackend.recv_multipart()
            MPbackend.send(address, flags=zmq.SNDMORE)
            MPbackend.send_json({'dtype': str(MP.dtype), 'shape': MP.shape}, flags=zmq.SNDMORE)
            MPbackend.send(MP, flags=0, copy=False, track=False)

        # If enough time elapsed... send stats via the result channel @ 5558 (PUSH socket)
        p1 = ptime.time()
        if p1 - p0 > 0.5:
            if Nprocessed > 0:
                stats = {'worker': wrk_num, 'processed': Nprocessed, 'hits': Nhits}
                results_sender.send_json(stats)
                Nprocessed = 0
                Nhits = 0
                p0 = p1

    backend.close()
    MPbackend.close()
    streamReceiver.close()
    results_sender.close()
    control_receiver.close()
    context0.term()
    Log("Worker %i exited properly" %wrk_num)


def loadBalancer(HF):

    """Load balancer main loop."""

    # Prepare context and sockets
    Log("Load Balancer Started")
    # frontend is connected to the GUI @ 5570
    context = zmq.Context.instance()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind('tcp://*:5570')
    #backend is connected to the workers @ 5571
    backend = context.socket(zmq.ROUTER)
    backend.bind("tcp://*:5571")

    workers = []
    i = 0
    showALL = False
    poller = zmq.Poller()

    # Only poll for requests from backend until workers are available
    poller.register(backend, zmq.POLLIN)
    #poller.register(frontend, zmq.POLLIN)

    while True:
        sockets = dict(poller.poll())

        # Handle worker activity on the backend
        # In this zmq socket, the first element of the message is its origin (identity of the sender, here Worker-i
        if backend in sockets:

            request = backend.recv_multipart()
            worker, message= request[:2]

            if message == b"START":  # At startup, sending the parameters back
                backend.send(worker, flags=zmq.SNDMORE)
                backend.send_json({'threshold': HF.threshold,
                                   'x1': HF.x1, 'x2': HF.x2, 'y1': HF.y1, 'y2': HF.y2,
                                   'npixels': HF.npixels, 'maskFN': HF.maskFN, 'shape':HF.shape})


            elif message == b"DATA COLLECTION START":
                # One of the worker received a message
                # Sending back to all workers the
                mxcube_dic = json.loads(request[2])
                Log("Load balancer sending MX Cube message")
                for wrk_num in range(HF.ncpus):
                    backend.send('Worker-%i'% wrk_num, flags=zmq.SNDMORE)
                    backend.send(b"DATA COLLECTION START",flags=zmq.SNDMORE)
                    backend.send_json(mxcube_dic)


            elif message != b"READY" and len(request) > 2:
                # This is a message corresponding to a hit
                # sjson holds the dtype and shape of the data
                # sxy holds the spot position and intensity
                sjson, sxy, data = request[2:]
                frontend.send_multipart([client, b"", sjson, sxy, data])

            # if showALL:
            # This is if you want to show all images
            #    if not workers:
            #        poller.register(frontend, zmq.POLLIN)
            #    if worker not in workers:
            #        workers.append(worker)

            # This snippet would be used to only show hits

            # Once a worker finds a hit, it sends a b"READY" message to the load balancer
            # The load balancer adds it to the 'available' workers
            # and register the frontend for polling now that a worker was available
            elif not showALL and message == b"READY":
                if not workers:
                    poller.register(frontend, zmq.POLLIN)

                if worker not in workers:
                    workers.append(worker)

            elif message == b'STOP':
                break

        # frontend is the gui
        if frontend in sockets:
            # Get next client request
            client, _, request = frontend.recv_multipart()
            if request == "HIT":
                # route to last-used worker
                if workers:
                    worker = workers.pop(0)
                    #print("LB: Received hit - will ask to %s" %worker)
                    backend.send_multipart([worker, b"", client, b"", request])
                    i += 1
                else:
                    #print("LB: Nothing to send")
                    sjson = "{'dtype': None, 'shape': None}"
                    frontend.send_multipart([client, b"", sjson, b""])
                    #frontend.send_multipart([client, b"", request])

    # Clean up at exit
    backend.close()
    frontend.close()
    context.term()
    Log("Load Balancer exited properly")

def send_multi(socket, origin, destination, request):
    getattr(socket,"send_multipart")([origin, b"", destination, b"", request])
    #socket.send_multipart([origin, b"", destination, b"", request])

def MPloadBalancer(HF):

    # Binning de 2 pour Max Proj si > 4M
    """Load balancer for Maximum Projection
    """
    # Prepare context and sockets
    Log("MP Load Balancer Started")
    # frontend is connected to the GUI @ 5560
    context = zmq.Context.instance()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind('tcp://*:5560')
    #backend is connected to the workers @ 5561
    backend = context.socket(zmq.ROUTER)
    backend.bind("tcp://*:5561")

    #workers_MP = []#["Worker-%i" for i in range(HF.ncpus)]
    #MP_count = 0
    poller = zmq.Poller()


    MP = np.zeros(HF.shape, dtype=np.int32)
    x = []
    y = []
    I = []
    poller.register(backend, zmq.POLLIN)
    poller.register(frontend, zmq.POLLIN)

    # Use timer to send request to workers
    timers = ZmqTimerManager()
    timer = ZmqTimer(3, send_multi, backend, [], "MaxProj-Client", "MAXPROJ")
    timers.add_timer(timer)

    while True:

        timers.check()
        sockets = dict(poller.poll(timers.get_next_interval()))

        # Handle worker activity on the backend
        if backend in sockets:

            request = backend.recv_multipart()
            worker, message = request[:2]

            if message == b"START":
                Log("MP balencer received start message from worker %s" %worker)
                timer.workers_MP.append(worker)

            if message == b"resetMP":
                MP[::] = 0

            if message != b"READY" and len(request) > 2:
                # If client reply, send rest back to frontend
                sjson= request[2]
                #print sjson
                #print(type(sjson))
                spots = json.loads(sjson)
                #buf = buffer(data)
                print(spots['spots'])
                #A = np.frombuffer(buf, dtype=md['dtype']).reshape(md['shape'])
                for spot in spots['spots']:
                    x.append(spot.x)
                    y.append(spot.y)
                    I.append(spot.intensity)

                MP[x, y] = I
                x = []
                y = []
                I = []
                #if HF.debug:
                #    MP = MP+A
                #    #Log("%i %s" %(MP.mean(),worker))
                #else:
                #    MP = np.maximum(MP, A)

            if message == b'STOP':
                break

        if frontend in sockets:
            #Log("Sending MP data to the client")
            client, _, request = frontend.recv_multipart()
            frontend.send_multipart([client, b"", sjson, MP])


    # Clean up
    backend.close()
    frontend.close()
    context.term()
    Log("MP Load Balancer exited properly")

def workerLCLS(wrk_num, HF, address):
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    #from psana import *
    ds = DataSource('exp=cxitut13:run=10:smd')
    det = Detector('DscCsPad')

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The Eiger stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    #print("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)
    #streamReceiver = context0.socket(zmq.PULL)
    # streamReceiver.connect("tcp://127.0.0.1:5557")
    #streamReceiver.connect("tcp://%s:9999"%HF.ip)


    # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
    results_sender = context0.socket(zmq.PUSH)
    results_sender.connect("tcp://%s:5558"%address)

    # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
    control_receiver = context0.socket(zmq.SUB)
    control_receiver.connect("tcp://%s:5559"%address)
    #Subscribe to all messages
    control_receiver.setsockopt(zmq.SUBSCRIBE, "")

    # Set up a channel to send messages to the load balancer (including images)
    #
    backend = zmq.Context().socket(zmq.DEALER)
    backend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
    backend.connect("tcp://%s:5571"%address)

    # send a start message to receive the parameters from the gui at startup...
    backend.send(b"START")
    newParams = backend.recv_json()

    for key in newParams.keys():
        if getattr(HF, key) is None:
            setattr(HF, key, newParams[key])

    if HF.maskFN is not None:
        HF.mask = openMask(HF.maskFN)
    ###

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(control_receiver, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)


    # Loop and accept messages from both channels, acting accordingly
    Nprocessed = 0
    Nhits = 0
    total = 0
    p0 = ptime.time()

    # MP = np.zeros(HF.detector.shape)
    #This is added when
    MP = np.zeros((2167,2070))
    data2SND = True


    while True:

        for nevent, evt in enumerate(ds.events()):
            if nevent % (size) != rank: continue





            calib_array = det.calib(evt)
            #print("Worker %i processing frame %i of series %i" %(wrk_num, frameID, seriesID ))
            Nprocessed += 1
            total += 1
            if HF.mask is not None:
                data = data * HF.mask
            #roi =  data[HF.x1:HF.x2, HF.y1:HF.y2]

            if data[ data > HF.threshold].size > HF.npixels:
                        Nhits += 1
                        hit = data
                        MP = np.maximum(MP, data)
                        if data2SND:
                            backend.send(b"READY")
                            data2SND = False

            socks = dict(poller.poll(1000))

            # If the message comes from the control channel, update parameters.
            if socks.get(control_receiver) == zmq.POLLIN:
                newParams = control_receiver.recv_json()

                # Resetting MP
                if newParams == b"resetMP":
                    MP[::] = 0

                # Stopping workers
                elif newParams == b"STOP":
                # Sending message to stop the LoadBalancer
                    if wrk_num == 0:
                        backend.send(b"STOP")
                    break
            # Updating Hit Finding parameters
                else:
                    newParams = control_receiver.recv_json()
                    for key in newParams.keys():
                        setattr(HF, key, newParams[key])
                        print("Setting %s to value: %s" %(key, str(newParams[key])))


            # If the message come from the load balancer - sending the image
            if socks.get(backend) == zmq.POLLIN:
                _, address, _, request = backend.recv_multipart()

                #Here depending on the request - send the appropriate data (hit ot max-proj)
                if request == "HIT":
                    backend.send(address, flags=zmq.SNDMORE)
                    backend.send_json({'dtype': str(data.dtype), 'shape': data.shape}, flags=zmq.SNDMORE)
                    backend.send(hit, flags=0, copy=False, track=False)
                    data2SND = True

                if request == "MAXPROJ":
                    #print("{}: {}".format(backend.identity.decode("ascii"),
                    #                      request.decode("ascii")))

                    backend.send(address, flags=zmq.SNDMORE)
                    backend.send_json({'dtype': str(MP.dtype), 'shape': MP.shape}, flags=zmq.SNDMORE)
                    backend.send(MP, flags=0, copy=False, track=False)


            # If enough time elapsed... send stats via the result channel @ 5558 (PUSH socket)
            p1 = ptime.time()
            if p1 - p0 > 0.5:
                if Nprocessed > 0:
                    stats = {'worker': wrk_num, 'processed': Nprocessed, 'hits': Nhits}
                    results_sender.send_json(stats)
                    Nprocessed = 0
                    Nhits = 0
                    p0 = p1

    backend.close()
    results_sender.close()
    control_receiver.close()
    context0.term()
    print("Worker %i exited properly" %wrk_num)
