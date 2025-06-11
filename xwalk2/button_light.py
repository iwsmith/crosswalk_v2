import sys
import zmq
from gpiozero import LED

from xwalk2.models import EndScene, PlayScene, parse_message
from xwalk2.util import heatbeat

def main():
  #  Socket to talk to server
  context = zmq.Context()
  socket = context.socket(zmq.SUB)
  led = LED(24)
  led.on()

  socket.connect("tcp://127.0.0.1:5557")

  t = heatbeat("button_light", "crosswalk-a")
  while True:
      try:
          action = parse_message(socket.recv_string())
          print(action)
      except KeyboardInterrupt:
          t.join()
          socket.close()
          context.term()
          sys.exit(0)
      if isinstance(action, PlayScene):
          led.off()
      elif isinstance(action, EndScene):
          led.on()

if __name__ == "__main__":
    main()