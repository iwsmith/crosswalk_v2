import zmq
from collections import defaultdict
from xwalk2.models import Heatbeat


def main():
    print("Starting Crosswalk V2 Controller...")
    print("Initializing ZMQ sockets...")

    context = zmq.Context()
    interactions = context.socket(zmq.SUB)
    interactions.bind("tcp://*:5556")
    interactions.setsockopt_string(zmq.SUBSCRIBE, "")

    control = context.socket(zmq.PUB)
    control.bind("tcp://*:5557")

    heartbeats = context.socket(zmq.SUB)
    heartbeats.bind("tcp://*:5558")
    heartbeats.setsockopt_string(zmq.SUBSCRIBE, "")

    print("ZMQ sockets initialized successfully")
    print("Listening on ports:")
    print("  - 5556: Interactions")
    print("  - 5557: Control")
    print("  - 5558: Heartbeats")
    print("\nController is running. Press Ctrl+C to exit.")
    print("Waiting for components to connect...\n")

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(interactions, zmq.POLLIN)
    poller.register(heartbeats, zmq.POLLIN)

    playing = False
    components = {}
    while True:
        print(components)
        try:
            socks = dict(poller.poll(1000))  # 1 second timeout
        except KeyboardInterrupt:
            print("\n🛑 Shutting down controller...")
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
                print("Reset sent to components")
            elif action == "A button pressed":
                if playing:
                    print("Currently playing; do nothing")
                else:
                    playing = True
                    control.send_string("Play scene")
                    print("Play command sent to components")

main()