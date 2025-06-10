
import zmq
from xwalk2.util import heatbeat


#  Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

socket.connect("tcp://127.0.0.1:5557")

# Subscribe to zipcode, default is NYC, 10001
socket.setsockopt_string(zmq.SUBSCRIBE, "")
lights_on = True
t = heatbeat("button_lights", "crosswalk-a")
while True:
    print(f"{lights_on=}")
    try:
      string = socket.recv_string()
      print(string)
    except KeyboardInterrupt:
       t.join()
    if string == "corgi":
        lights_on = False
    elif string == "reset":
      lights_on = True
