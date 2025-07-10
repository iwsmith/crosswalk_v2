from datetime import datetime
import logging

import zmq
from pydantic import BaseModel

from xwalk2.fsm import Controller
from xwalk2.models import (
    APIResponse,
    APIQueueClear,
    APIQueueWalk,
    APIStatusRequest,
    APIButtonPress,
    APITimerExpired,
    ButtonPress,
    CurrentState,
    Heatbeat,
    TimerExpired,
    parse_message,
    parse_api
)

logger = logging.getLogger(__name__)

def main():
    print("Starting Crosswalk V2 Controller with FSM...")
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

    def make_response(message: str = "", success: bool = True) -> APIResponse:
        """Create a standard API response"""
        return  APIResponse(
            success=success,
            message=message,
            playing=playing,
            components=components,
            timestamp=datetime.now(),
            state=state.state,
            animations=state.animations.config,
            walk_queue=state.walk_queue,
            walk_history=state.walk_history,
            active_schedule=state.animations.get_active_schedule(),
            menu=state.animations.config.menu,
        )

    def handle_api_request(request: BaseModel) -> APIResponse:
        """Handle API requests and return a response"""
        if isinstance(request, APIQueueWalk):
            if request.walk == '_':
                for categories in state.animations.config.walks.values():
                    state.walk_queue.extend(categories.keys())
                return make_response(message=f"All walks queued. {len(state.walk_queue)} total queued.")
            else:
                state.walk_queue.append(request.walk)
                return make_response(message=f"Walk '{request.walk}' queued. {len(state.walk_queue)} total queued.")
        elif isinstance(request, APIQueueClear):
            state.walk_queue.clear()
            return make_response(message="Walk queue cleared")
        elif isinstance(request, APIButtonPress):
            # Handle button press action
            state.button_press()
            return make_response(message="Button pressed")
        elif isinstance(request, APITimerExpired):
            # Handle timer expired event
            state.timer_expired()
            return make_response(message="Timer expired event sent")
        elif isinstance(request, APIStatusRequest):
            # Handle status request
            return make_response()
        else:
            logger.warning(f"Received unknown API request type: {type(request)}")
            return make_response(message=f"Invalid request type {type(request)}", success=False)

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
                    api_request = parse_api(request_data)
                    response = handle_api_request(api_request)
                    # Send response
                    api_socket.send_string(response.model_dump_json())

                except Exception as e:
                    logger.error("Error handling API request", exc_info=True)
                    # Send error response
                    error_response = make_response(
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
                    logger.error("💥 Error handling interaction", exc_info=True)

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
            logger.error("⚠️  Error during cleanup", exc_info=True)


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
