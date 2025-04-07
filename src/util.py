import threading
import zmq
import time
from models import Heatbeat
from datetime import datetime


def heatbeat(component, host, every_s=10):
  def _beat():
    context = zmq.Context.instance()
    socket = context.socket(zmq.PUB)
    socket.connect("tcp://127.0.0.1:5558")
    while True:
      print(f"{component} beating")
      socket.send_string(Heatbeat(host=host, component=component, sent_at=datetime.now()).model_dump_json())
      time.sleep(every_s)

  thread = threading.Thread(target=_beat)
  thread.start()
  return thread

