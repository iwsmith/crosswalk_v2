
import zmq
import time
from util import heatbeat


#  Socket to talk to server
context = zmq.Context()
control = context.socket(zmq.SUB)
control.connect("tcp://127.0.0.1:5557")
control.setsockopt_string(zmq.SUBSCRIBE, "C")

interaction = context.socket(zmq.PUB)
interaction.connect("tcp://127.0.0.1:5556")

t = heatbeat("timer", "crosswalk-a")

while True:
  try:
    string = control.recv_string()
  except KeyboardInterrupt:
    t.join()
  if string == "C Play scene":
    print("Scene started, sleep for 10.1s")
    time.sleep(01.1)
    interaction.send_string("A Timer fired")
