from datetime import datetime

import zmq

from xwalk2.models import APIRequest, APIResponse, Heatbeat, parse_message, ButtonPress
from xwalk2.fsm import Controller


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

    # Unified API socket for both status and action requests
    api_socket = context.socket(zmq.REP)
    api_socket.bind("tcp://*:5559")

    print("ZMQ sockets initialized successfully")
    print("Listening on ports:")
    print("  - 5556: Interactions")
    print("  - 5557: Control")
    print("  - 5558: Heartbeats")
    print("  - 5559: API Requests")
    print("\nController is running. Press Ctrl+C to exit.")
    print("Waiting for components to connect...\n")

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(interactions, zmq.POLLIN)
    poller.register(heartbeats, zmq.POLLIN)
    poller.register(api_socket, zmq.POLLIN)

    state = Controller()

    playing = False
    components = {}

    def send_string(s):
        print(f"Sending: {s}")
        control.send_string(s)

    while True:
        #print(components)
        print(state.state)
        try:
            socks = dict(poller.poll(1000))  # 1 second timeout
        except KeyboardInterrupt:
            print("\n🛑 Shutting down controller...")
            break

        if heartbeats in socks:
            beat = Heatbeat.model_validate_json(heartbeats.recv_string())
            print(f"Got {beat=}")
            components[beat.component] = beat.sent_at

        if api_socket in socks:
            try:
                # Receive API request
                request_data = api_socket.recv_string()
                api_request = APIRequest.model_validate_json(request_data)

                if api_request.request_type == "status":
                    # Handle status request
                    response = APIResponse(
                        success=True,
                        message="Status retrieved successfully",
                        playing=playing,
                        components=components,
                        timestamp=datetime.now(),
                    )

                elif api_request.request_type == "action":
                    # Handle action request
                    if api_request.action:
                        success, message = handle_action(api_request.action)
                        response = APIResponse(
                            success=success,
                            message=message,
                        )
                        print(f"Processed action '{api_request.action}': {message}")
                    else:
                        response = APIResponse(
                            success=False,
                            message="Action request missing action field",
                        )
                else:
                    response = APIResponse(
                        success=False,
                        message=f"Unknown request type: {api_request.request_type}",
                    )

                # Send response
                api_socket.send_string(response.model_dump_json())

            except Exception as e:
                print(f"Error handling API request: {e}")
                # Send error response
                error_response = APIResponse(
                    success=False,
                    message=f"Server error: {str(e)}",
                )
                api_socket.send_string(error_response.model_dump_json())

        if interactions in socks:
            # Handle interactions from other components (like button_switch)
            action = parse_message(interactions.recv_string())
            if isinstance(action, ButtonPress):
                state.button_press(send_string)


main()
