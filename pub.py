
import zmq
from random import randrange
import time


context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://127.0.0.1:5556")

pid = randrange(100)
while True:

    socket.send_json({"key":"corgi", "value":"long"})
    time.sleep(1)