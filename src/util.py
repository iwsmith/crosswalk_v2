import threading
import zmq
import time


def heatbeat(component, host, every_s=10):
  def _beat():
    context = zmq.Context.instance()
    socket = context.socket(zmq.PUB)
    socket.connect("tcp://127.0.0.1:5558")
    while True:
      print(f"{component} beating")
      socket.send_json({"host":host,"component":component,"sent_at":time.time()})
      time.sleep(every_s)

  thread = threading.Thread(target=_beat)
  thread.start()
  return thread

