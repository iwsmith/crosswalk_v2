import sys
import zmq
from gpiozero import LED

from xwalk2.models import EndScene, PlayScene, CurrentState, parse_message
from xwalk2.util import heatbeat


def main():
    #  Socket to talk to server
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    led = LED(24)
    led.off()

    socket.connect("tcp://127.0.0.1:5557")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    t = heatbeat("button_light", "crosswalk-a")
    while True:
        try:
            msg = socket.recv_string()
            action = parse_message(msg)
            if isinstance(action, PlayScene):
                led.off()
            elif isinstance(action, EndScene):
                led.on()
            elif isinstance(action, CurrentState):
                if action.state == "playing":
                    led.off()
                else:
                    led.on()
        except KeyboardInterrupt:
            t.join()
            socket.close()
            context.term()
            sys.exit(0)
              


if __name__ == "__main__":
    main()
