from datetime import datetime
import logging

import zmq
from pydantic import BaseModel

from xwalk2.fsm import Controller
from xwalk2.models import (
    APIRequest,
    APIResponse,
    ButtonPress,
    CurrentState,
    Heatbeat,
    TimerExpired,
    parse_message,
)

logger = logging.getLogger(__name__)

def main():
    print("Starting Crosswalk V2 Controller with FSM...")
    print("Initializing animation library...")

    # Initialize animation library (crash early if not available)
    print("Animation library loaded successfully")
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
    print("Controller is running. Press Ctrl+C to exit.")
    print("Waiting for components to connect...\n")

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(interactions, zmq.POLLIN)
    poller.register(heartbeats, zmq.POLLIN)
    poller.register(api_socket, zmq.POLLIN)

    def send_command(command_obj: BaseModel):
        """Send command as consistent JSON"""
        command_json = command_obj.model_dump_json()
        control.send_string(command_json)

    # Initialize FSM controller
    state = Controller(send_command)

    playing = False
    components = {}

    def handle_api_action(action: str) -> tuple[bool, str]:
        """Handle API actions - now calls consolidated handlers"""
        if action == "button_pressed":
            state.button_press()
        elif action == "timer_expired":
            state.timer_expired()
        elif action == "reset":
            state.reset()()
        else:
            return False, f"Unknown action: {action}"
        return True, "Whatever"

    # Main control loop, wrapped in try for graceful shutdown
    last_state = state.state
    print(f"🎛️  FSM State: {state.state} | Playing: {playing}")
    try:
        while True:
            # Update playing status based on FSM state, but only when changed
            if state.state != last_state:
                playing = state.state == "walk"
                print(f"🎛️  FSM State: {state.state} | Playing: {playing}")
                last_state = state.state

            new_component = False
            try:
                socks = dict(poller.poll(1000))  # 1 second timeout
            except KeyboardInterrupt:
                print("\nShutting down controller...")
                break

            if heartbeats in socks:
                beat = Heatbeat.model_validate_json(heartbeats.recv_string())
                component_name = f"{beat.component}/{beat.host}"
                if component_name not in components or beat.initial:
                    logger.info(f"{component_name} sent {beat.initial} or {component_name in components}")
                    new_component = True
                components[component_name] = beat.sent_at

            # If there is a new component it will need our current state
            if new_component:
                logger.info("Sending initial state")
                current_state = CurrentState(state=state.state)
                send_command(current_state)

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
                            state=state.state,
                            animations=state.animations.config
                        )

                    elif api_request.request_type == "action":
                        # Handle action request
                        if api_request.action:
                            success, message = handle_api_action(api_request.action)
                            response = APIResponse(
                                success=success,
                                message=message,
                            )
                            print(
                                f"🎮 Processed action '{api_request.action}': {message}"
                            )
                        else:
                            response = APIResponse(
                                success=False,
                                message="Action request missing action field",
                            )
                    elif api_request.request_type == "reset":
                        # Handle reset using consolidated handler
                        success, message = handle_api_action(api_request.action)
                        response = APIResponse(success=success, message=message)
                    else:
                        response = APIResponse(
                            success=False,
                            message=f"Unknown request type: {api_request.request_type}",
                        )

                    # Send response
                    api_socket.send_string(response.model_dump_json())

                except Exception as e:
                    print(f"💥 Error handling API request: {e}")
                    # Send error response
                    error_response = APIResponse(
                        success=False,
                        message=f"Server error: {str(e)}",
                    )
                    api_socket.send_string(error_response.model_dump_json())

            if interactions in socks:
                # Handle interactions from other components
                interaction_data = interactions.recv_string()
                print(f"📨 Received interaction: {interaction_data}")

                try:
                    action = parse_message(interaction_data)

                    if isinstance(action, ButtonPress):
                        state.button_press()

                    elif isinstance(action, TimerExpired):
                        state.timer_expired()
                    
                except Exception as e:
                    print(f"💥 Error parsing interaction: {e}")

    except KeyboardInterrupt:
        print("\nController interrupted")
        # TODO: Add state shutdown
    finally:
        # Cleanup
        print("🧹 Cleaning up controller...")
        try:
            interactions.close(0)
            control.close(1)
            heartbeats.close(0)
            api_socket.close(0)
            context.term()
            print("Controller cleanup complete")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    main()
