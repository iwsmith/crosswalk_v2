import zmq

def event_bus():
    context = zmq.Context()
    frontend = context.socket(zmq.XSUB)  # For publishers
    backend = context.socket(zmq.XPUB)  # For subscribers

    frontend.bind("tcp://*:5556")
    backend.bind("tcp://*:5557")

    zmq.proxy(frontend, backend)  # Proxy messages between publishers and subscribers

if __name__ == "__main__":
    event_bus()
