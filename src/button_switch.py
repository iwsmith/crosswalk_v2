

import zmq


#  Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.PUB)

socket.connect("tcp://127.0.0.1:5556")


while True:
    input("Press enter to trigger button")
    socket.send_string("A button pressed")