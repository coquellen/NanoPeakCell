from ZmqSockets import EigerZMQStream, EigerStreamDecoder
from pyqtgraph import ptime
import zmq
import time
import numpy as np
import h5py

def openMask(fn):
    h51 = h5py.File(fn, 'r')
    data = -1 * (h51['data'][:] - 1)
    h51.close()
    return data

def worker_debug(wrk_num, HF):
    #h5 = h5py.File('/Users/coquelleni/PycharmProjects/NanoPeakCell_0.3.2/NPC_DATA/tcache_2_358_data_000020.h5', 'r')
    #h5 = h5py.File('/gz/data/id13/inhouse4/THEDATA_I4_1/d_2016-03-02_user_ls2458/DATA/AUTO-TRANSFER/eiger2/lys9_22_data_00030%i.h5' %wrk_num, 'r')

    # Initialize a zeromq context
    context0 = zmq.Context()

    # The Eiger stream is a push socket on port 9999
    # Setup a Pull socket to get data from stream
    print("Initializing the ZMQ Pull socket to get the Eiger stream at ip %s" %HF.ip)
    streamReceiver = context0.socket(zmq.PULL)
    # streamReceiver.connect("tcp://127.0.0.1:5557")
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
        HF.mask = openMask(HF.maskFN)
    ###

    # Set up a poller to multiplex the work receiver and control receiver channels
    poller = zmq.Poller()
    poller.register(streamReceiver, zmq.POLLIN)
    poller.register(control_receiver, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)

    streamDecoder = EigerStreamDecoder()

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

        socks = dict(poller.poll(1000))

        # If the message comes from Eiger stream,
        if socks.get(streamReceiver) == zmq.POLLIN:

            frames = streamReceiver.recv_multipart(copy=False)
            seriesID, frameID, data = streamDecoder.decodeFrames(frames)

            #the decodeFrames returns -1 for the header
            # and -2 for the end of series messages
            if frameID >= 0:
                print("Worker %i processing frame %i of series %i" %(wrk_num, frameID, seriesID ))
                if (HF.RADDAM and (frameID % HF.NShots) == 1) or not HF.RADDAM:
                    # If HF.RADDAM, only process one frames for every HF.NShots
                    # The 1 means that the second frame of each raster scanning position is used to take into account the opening of the shutter
                    # frame 0 is not used
                    #if not HF.RADDAM (i.e fast scan - process all frames)
                    Nprocessed += 1
                    total += 1
                    if HF.mask is not None:
                        data = data * HF.mask
                    roi =  data[HF.x1:HF.x2, HF.y1:HF.y2]

                    if roi[ roi > HF.threshold].size > HF.npixels:
                        Nhits += 1
                        hit = data
                        MP = np.maximum(MP, data)
                        if data2SND:
                            backend.send(b"READY")
                            data2SND = False

            #This is the final message
            #if N == -1:
            elif frameID == -2:
                backend.send(b"End of Series")
                #results_sender.send(b"End of Series")

            elif frameID == -3:
                print("Worker %i received a non ZMQ Eiger message.... Weird...")


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
    streamReceiver.close()
    results_sender.close()
    control_receiver.close()
    context0.term()
    print("Worker %i exited properly" %wrk_num)

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

def loadBalancer(HF):

    """Load balancer main loop."""

    # Prepare context and sockets
    print("Load Balancer Started")
    # frontend is connected to the GUI @ 5570
    context = zmq.Context.instance()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind('tcp://*:5570')
    #backend is connected to the workers @ 5571
    backend = context.socket(zmq.ROUTER)
    backend.bind("tcp://*:5571")

    workers = []
    workers_MP = []
    MP_count = 0
    showALL = False
    poller = zmq.Poller()

    # Only poll for requests from backend until workers are available
    poller.register(backend, zmq.POLLIN)

    while True:
        sockets = dict(poller.poll())

        if backend in sockets:

            # Handle worker activity on the backend
            request = backend.recv_multipart()
            worker, client = request[:2]


            if client == b"START":
                workers_MP.append(worker)
                backend.send(worker, flags = zmq.SNDMORE)
                backend.send_json({'threshold': HF.threshold,
                                   'x1': HF.x1, 'x2': HF.x2, 'y1': HF.y1, 'y2': HF.y2,
                                   'npixels': HF.npixels, 'maskFN': HF.maskFN})

            if client != b"READY" and len(request) > 2:
                # If client reply, send rest back to frontend
                json, data = request[2:]
                frontend.send_multipart([client, b"", json, data])



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
                if not workers:
                    poller.register(frontend, zmq.POLLIN)
                workers.append(worker)

            if client == b'STOP':
                break

        if frontend in sockets:
            # Get next client request (HIT or MAXPROJ)
            client, empty, request = frontend.recv_multipart()

            if request == "HIT":
                # route to last-used worker
                worker = workers.pop(0)
                backend.send_multipart([worker, b"", client, b"", request])
                # Don't poll clients if no workers are available
                if not workers:
                    poller.unregister(frontend)

            elif request == "MAXPROJ":
                backend.send_multipart([workers_MP[MP_count % len(workers_MP)], b"", client, b"", request])
                MP_count += 1

            #Not implemented yet ...
            elif request == "ALL":
                showALL = True

            elif request == "ONLY":
                showALL = False

    # Clean up
    backend.close()
    frontend.close()
    context.term()
    print("Load Balancer exited properly")


