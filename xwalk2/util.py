import threading
import zmq
import time
from xwalk2.models import Heatbeat
from datetime import datetime


def heatbeat(component, host, every_s=10):
    stop_event = threading.Event()

    def _beat():
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUB)
        socket.connect("tcp://127.0.0.1:5558")
        try:
            while not stop_event.is_set():
                print(f"{component} beating")
                socket.send_string(Heatbeat(host=host, component=component, sent_at=datetime.now()).model_dump_json())
                time.sleep(every_s)
        finally:
            socket.close()
            context.term()

    thread = threading.Thread(target=_beat)
    thread.daemon = True
    thread.start()

    def stop():
        stop_event.set()
        thread.join(timeout=1.0)

    thread.stop = stop
    return thread

