import zmq
from collections import defaultdict
from models import Heatbeat

def main():

    context = zmq.Context()
    interactions = context.socket(zmq.SUB)
    interactions.bind("tcp://*:5556")
    interactions.setsockopt_string(zmq.SUBSCRIBE, "")

    control = context.socket(zmq.PUB)
    control.bind("tcp://*:5557")

    heartbeats = context.socket(zmq.SUB)
    heartbeats.bind("tcp://*:5558")
    heartbeats.setsockopt_string(zmq.SUBSCRIBE, "")

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(interactions, zmq.POLLIN)
    poller.register(heartbeats, zmq.POLLIN)

    playing = False
    components = {}
    while True:
        print(components)
        try:
            socks = dict(poller.poll())
        except KeyboardInterrupt:
            break

        if heartbeats in socks:
            beat = Heatbeat.model_validate_json(heartbeats.recv_string())
            print(f"Got {beat=}")

            components[beat.component] = beat.sent_at

        if interactions in socks:
            action = interactions.recv_string()
            print(action)
            if action == "A Timer fired":
                playing = False
                control.send_string("C RESET")
            elif action == "A button pressed":
                if playing:
                    print("Currently playing; do nothing")
                else:
                    playing = True
                    control.send_string("Play scene")

main()