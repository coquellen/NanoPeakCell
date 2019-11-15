from pyqtgraph import ptime
import zmq
import time
import numpy as np
import h5py
import requests
import json
from NPC.utils import Log
from NPC.gui.ZmqSockets import ZmqTimerManager, ZmqTimer

def openMask(fn):
    h51 = h5py.File(fn, 'r')
    data = -1 * (h51['data'][:] - 1)
    h51.close()
    return data.astype(np.int32)

def ventilator():
    # Initialize a zeromq context
    context = zmq.Context()

    # Set up a channel to send work
    ventilator_send = context.socket(zmq.PUSH)
    ventilator_send.bind("tcp://127.0.0.1:5557")

    # Give everything a second to spin up and connect
    time.sleep(1)

    # Send the numbers between 1 and 1 million as work messages
    num = 0
    while num < 10000:
        work_message = { 'num' : num }
        #print("Ventilator Sent %i" % num)
        num += 1
        ventilator_send.send_json(work_message)

        #time.sleep(0.01)


    #time.sleep(1)
    print("Ventilator Done")

def workerEuXFEL(wrk_num, HF):
    from karabo_bridge import Client

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The Eiger stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    if wrk_num == 0:
        Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)

    streamReceiver = context0.socket(zmq.PULL)
    streamReceiver.connect("tcp://%s:9999"%HF.ip)
    client = Client('tcp://10.253.0.51:45010')

    # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
    results_sender = context0.socket(zmq.PUSH)
    results_sender.connect("tcp://127.0.0.1:5558")

    # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
    control_receiver = context0.socket(zmq.SUB)
    control_receiver.connect("tcp://127.0.0.1:5559")
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
        MP = np.zeros((16,512,128), dtype=np.int32)

    data2SND = True
    hit_IDX = []
    nohit_IDX = []


    while True:
        socks = dict(poller.poll())


        # If the message came over the control channel, update parameters.
        if socks.get(streamReceiver) == zmq.POLLIN:
            data = streamReceiver.recv_json()

            #data = client.next()
            array = data[0]['SPB_DET_AGIPD1M-1/CAL/APPEND_CORRECTED']['image_data'].shape
            Nprocessed += array.shape[0]
            total += array.shape[0]
            if HF.mask is not None:
                data = data * HF.mask
            # roi = data[HF.x1:HF.x2, HF.y1:HF.y2]

            hits = np.where(np.count_nonzero(data > HF.threshold, axis=(1, 2, 3)) >= HF.npixels)
            # hit = data
            # if roi[roi > HF.threshold].size > HF.npixels:
            Nhits += 1
            hit = data[0, :, :]
            if HF.computeMP:
                MP = np.maximum(MP, np.amax(data, axis=0))
            if data2SND:
                backend.send(b"READY")
                data2SND = False
                # else:
                #    nohit_IDX.append(frameID)

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


def workerEiger(wrk_num, HF):
    from NPC.gui.ZmqSockets import EigerStreamDecoder
    #This class has been generously provided by Sacha Grimm from Dectris, and slightly modified for our implementation
    streamDecoder = EigerStreamDecoder()

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The Eiger stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    if wrk_num == 0:
        Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)

    streamReceiver = context0.socket(zmq.PULL)
    streamReceiver.connect("tcp://%s:9999"%HF.ip)


    # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
    results_sender = context0.socket(zmq.PUSH)
    results_sender.connect("tcp://127.0.0.1:5558")

    # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
    control_receiver = context0.socket(zmq.SUB)
    control_receiver.connect("tcp://127.0.0.1:5559")
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
        # If the message comes from Eiger stream,
        if socks.get(streamReceiver) == zmq.POLLIN:

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
                    Log("--- Dropped %i images --" % dropped)
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

def onlineSACLA(wrk_num, HF, host):
    #This class has been generously provided by Sacha Grimm from Dectris, and slightly modified for our implementation
    #streamDecoder = EigerStreamDecoder()

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The zmq stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    if wrk_num == 0:
        Log("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)

    streamReceiver = context0.socket(zmq.PULL)
    streamReceiver.connect("tcp://%s:9999"%HF.ip)


    # Set up a channel to send result of work to the results reporter (PUSH socket @ port 5558)
    results_sender = context0.socket(zmq.PUSH)
    results_sender.connect("tcp://127.0.0.1:5558")

    # Set up a channel to receive control messages over directly from the GUI(SUB socket @ port 5559)
    control_receiver = context0.socket(zmq.SUB)
    control_receiver.connect("tcp://127.0.0.1:5559")
    #Subscribe to all messages
    control_receiver.setsockopt(zmq.SUBSCRIBE, "")

    # Set up a channel to send messages to the load balancer (including images)
    #
    backend = zmq.Context().socket(zmq.DEALER)
    backend.identity = u"Worker-{}".format(wrk_num).encode("ascii")
    backend.connect("tcp://localhost:5571")

    # send a start message to receive the parameters from the gui at startup...
    backend.send(b"START")
    newParams = backend.recv_json()

    for key in newParams.keys():
        if getattr(HF, key) is None:
            setattr(HF, key, newParams[key])

    if HF.maskFN is not None:
        import time
        time.sleep(wrk_num/2.)
        HF.mask = openMask(HF.maskFN)
    ###

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(streamReceiver, zmq.POLLIN)
    poller.register(control_receiver, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)


    # Loop and accept messages from both channels, acting accordingly
    Nprocessed = 0
    Nhits = 0
    total = 0
    p0 = ptime.time()
    data = None

    # MP = np.zeros(HF.detector.shape)
    #This is added when

    MP = np.zeros(HF.shape)
    data2SND = True
    hit_IDX = []
    nohit_IDX = []

    while True:

        socks = dict(poller.poll(1000))

        # If the message comes from Eiger stream,
        if socks.get(streamReceiver) == zmq.POLLIN:

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
                    Log("Eiger series started: %s " % name_pattern.replace('$id', str(seriesID)))
                    results_sender.send_json({"name_pattern": name_pattern, "series": seriesID})

            elif frameID == -2:
                r = requests.get("http://%s/stream/api/1.3.1/status/dropped" % HF.ip)
                # results_sender.send_json(stats)
                if r.status_code == 200:
                    dropped = r.json()["value"]
                    Log("--- End of series ---")
                    Log("--- Dropped %i images" % dropped)
                    results_sender.send_json({"End": dropped})
                    # backend.send(b"End of Series")

            elif frameID == -3:
                Log("Worker %i received a non ZMQ Eiger message... Weird...")


        # If the message came over the control channel, update parameters.
        if socks.get(control_receiver) == zmq.POLLIN:
            newParams = control_receiver.recv_json(zmq.NOBLOCK)
            #if wrk_num == 0:


            if newParams.keys()[0] in ["STOP", "resetMP"]:
                key = newParams.keys()[0]
                if newParams[key] == "resetMP":
                    MP[::] = 0
                    if wrk_num == 0:
                        Log("Message received from Control Gui: Resetting MP")


                elif newParams[key] == "STOP":
                    if wrk_num == 0:
                        backend.send(b"STOP")
                        Log("Message received from Control Gui: exiting")

                    break

            else:
                for key in newParams.keys():
                    setattr(HF, key, newParams[key])
                    if wrk_num == 0:
                        Log("Message received from Control Gui: Setting %s to value %s"%(key,str(newParams[key])))

        if socks.get(backend) == zmq.POLLIN:
            _, address, _, request = backend.recv_multipart()
            # Here depending on the request - send the appropriate data (hit ot max-proj)
            if request == "HIT":
                # print("{}: {}".format(backend.identity.decode("ascii"),
                #                  request.decode("ascii")))
                if hasattr(data, 'shape'):
                    backend.send(address, flags=zmq.SNDMORE)
                    backend.send_json({'dtype': str(data.dtype), 'shape': data.shape}, flags=zmq.SNDMORE)
                    backend.send(hit, flags=0, copy=False, track=False)
                    data2SND = True

            if request == "MAXPROJ":
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
    showALL = False
    poller = zmq.Poller()

    # Only poll for requests from backend until workers are available
    poller.register(backend, zmq.POLLIN)
    poller.register(frontend, zmq.POLLIN)

    while True:
        sockets = dict(poller.poll())
        if backend in sockets:

            # Handle worker activity on the backend
            request = backend.recv_multipart()
            worker, client = request[:2]

            if client == b"START":
                backend.send(worker, flags = zmq.SNDMORE)
                backend.send_json({'threshold': HF.threshold,
                                   'x1': HF.x1, 'x2': HF.x2, 'y1': HF.y1, 'y2': HF.y2,
                                   'npixels': HF.npixels, 'maskFN': HF.maskFN, 'shape':HF.shape})

            if client != b"READY" and len(request) > 2:
                # If client reply, send rest back to frontend
                sjson, data = request[2:]
                frontend.send_multipart([client, b"", sjson, data])



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
            if not showALL and client == b"READY":
                #if not workers:
                    #poller.register(frontend, zmq.POLLIN)
                workers.append(worker)

            if client == b'STOP':
                break

        if frontend in sockets:
            # Get next client request
            client, _, request = frontend.recv_multipart()
            if request == "HIT":
                # route to last-used worker
                if workers:
                    worker = workers.pop(0)
                    backend.send_multipart([worker, b"", client, b"", request])
                else:
                    frontend.send_multipart([client, b"", request])

            #Not implemented yet ...
            #elif request == "ALL":
            #    showALL = True

            #elif request == "ONLY":
            #    showALL = False

    # Clean up
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

    poller.register(backend, zmq.POLLIN)
    poller.register(frontend, zmq.POLLIN)

    timers = ZmqTimerManager()
    timer = ZmqTimer(3, send_multi, backend, [], "MaxProj-Client", "MAXPROJ")
    timers.add_timer(timer)

    while True:

        timers.check()
        sockets = dict(poller.poll(timers.get_next_interval()))

        if backend in sockets:

            # Handle worker activity on the backend
            request = backend.recv_multipart()
            worker, client = request[:2]

            if client == b"START":
                timer.workers_MP.append(worker)

            if client == b"resetMP":
                MP[::] = 0

            if client != b"READY" and len(request) > 2:
                # If client reply, send rest back to frontend
                sjson, data = request[2:]
                md = json.loads(sjson)
                buf = buffer(data)
                A = np.frombuffer(buf, dtype=md['dtype']).reshape(md['shape'])
                #
                if HF.debug:
                    MP = np.maximum(MP, A)
                    #Log("%i %s" %(MP.mean(),worker))
                else:
                    MP = np.maximum(MP, A)

            if client == b'STOP':
                break

        if frontend in sockets:

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
