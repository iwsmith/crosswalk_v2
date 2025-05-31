
import zmq
from util import heatbeat


#  Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

socket.connect("tcp://127.0.0.1:5557")

socket.setsockopt_string(zmq.SUBSCRIBE, "")

print("WAIT")
t = heatbeat("matrix_drive", "crosswalk-a")
while True:
  try:
    string = socket.recv_string()
  except KeyboardInterrupt:
    t.join()
  print(string)
  if string == "C Play scene":
    print("WALK SIGN IS ON")
  elif string == "C RESET":
    print("WAIT")
