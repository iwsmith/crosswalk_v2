
import zmq


#  Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

socket.connect("tcp://127.0.0.1:5557")

# Subscribe to zipcode, default is NYC, 10001
socket.setsockopt_string(zmq.SUBSCRIBE, "C")

print("WAIT")
while True:
    string = socket.recv_string()
    if string == "C Play scene":
      print("WALK SIGN IS ON")
    elif string == "C RESET":
      print("WAIT")
