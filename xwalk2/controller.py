import json
from datetime import datetime

import zmq

from xwalk2.fsm import Controller
from xwalk2.models import (
    APIRequest,
    APIResponse,
    ButtonPress,
    Heatbeat,
    CurrentState,
    EndScene,
    PlayScene,
    ResetCommand,
    parse_message,
)
from xwalk2.animation_library import AnimationLibrary


def main():
    print("Starting Crosswalk V2 Controller with FSM...")
    print("Initializing animation library...")
    
    # Initialize animation library (crash early if not available)
    animation_lib = AnimationLibrary()
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
    print("\Controller is running. Press Ctrl+C to exit.")
    print("Waiting for components to connect...\n")

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(interactions, zmq.POLLIN)
    poller.register(heartbeats, zmq.POLLIN)
    poller.register(api_socket, zmq.POLLIN)

    # Initialize FSM controller
    state = Controller()

    playing = False
    components = {}

    def send_command(command_obj):
        """Send command as consistent JSON"""
        command_json = command_obj.model_dump_json()
        print(f"📤 Sending: {command_json}")
        control.send_string(command_json)

    def handle_reset() -> tuple[bool, str]:
        """Handle reset action - consolidated logic"""
        state.reset()
        print(f"🎛️  FSM transition: {state.state} -> ready")
        
        reset_command = ResetCommand()
        send_command(reset_command)
        return True, "System reset command sent"

    def handle_timer_expired() -> tuple[bool, str]:
        """Handle timer expired action - consolidated logic"""
        state.reset()
        print(f"🎛️  FSM transition: {state.state} -> ready")
        
        reset_command = ResetCommand()
        send_command(reset_command)
        return True, "Timer expired - reset command sent"

    def handle_button_pressed() -> tuple[bool, str]:
        """Handle button pressed action - consolidated logic"""
        if playing:
            return False, "Already playing - action ignored"
        else:
            # Trigger FSM transition to 'walk' state
            state.button_press()
            print(f"🎛️  FSM transition: ready -> walk")
            
            # Select sophisticated animation sequence
            intro, walk, outro = animation_lib.select_animation_sequence()
            
            # Get durations for timing
            intro_duration, walk_duration, outro_duration = animation_lib.get_sequence_durations(
                intro, walk, outro
            )
            total_duration = intro_duration + walk_duration + outro_duration
            
            # Create PlayScene
            play_command = PlayScene(
                intro=intro,
                walk=walk,
                outro=outro,
                intro_duration=intro_duration,
                walk_duration=walk_duration,
                outro_duration=outro_duration,
                total_duration=total_duration
            )
            
            print(f"🎬 Controller: Selected animation sequence: {intro} -> {walk} -> {outro}")
            
            # Send command
            send_command(play_command)
            
            return True, f"Animation sequence started: {intro} -> {walk} -> {outro}"

    def handle_api_action(action: str) -> tuple[bool, str]:
        """Handle API actions - now calls consolidated handlers"""
        if action == "button_pressed":
            return handle_button_pressed()
        elif action == "timer_expired":
            return handle_timer_expired()
        elif action == "reset":
            return handle_reset()
        else:
            return False, f"Unknown action: {action}"

    # Main control loop, wrapped in try for graceful shutdown
    try:
        while True:
            # Update playing status based on FSM state
            playing = (state.state == 'walk')
            print(f"🎛️  FSM State: {state.state} | Playing: {playing}")

            new_component = False
            try:
                socks = dict(poller.poll(1000))  # 1 second timeout
            except KeyboardInterrupt:
                print("\n🛑 Shutting down controller...")
                break

            if heartbeats in socks:
                beat = Heatbeat.model_validate_json(heartbeats.recv_string())
                # print(f"Got {beat=}")
                if beat not in components:
                    new_component = True
                components[beat] = beat.sent_at

            # If there is a new component it will need our current state
            if new_component:
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
                        )

                    elif api_request.request_type == "action":
                        # Handle action request
                        if api_request.action:
                            success, message = handle_api_action(api_request.action)
                            response = APIResponse(
                                success=success,
                                message=message,
                            )
                            print(f"🎮 Processed action '{api_request.action}': {message}")
                        else:
                            response = APIResponse(
                                success=False,
                                message="Action request missing action field",
                            )
                    elif api_request.request_type == "reset":
                        # Handle reset using consolidated handler
                        success, message = handle_reset()
                        response = APIResponse(
                            success=success, 
                            message=message
                        )
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
                        print(f"🔘 Button press from {action.component} ({action.press_duration}ms)")
                        success, message = handle_button_pressed()
                        print(f"🎮 Button interaction result: {message}")
                    
                    elif isinstance(action, EndScene):
                        print(f"⏰ Timer expired: {action.timer_id} after {action.duration:.2f}s")
                        success, message = handle_timer_expired()
                        print(f"🎮 Timer interaction result: {message}")
                    
                    else:
                        print(f"📋 Other structured message: {type(action).__name__}")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"❓ Invalid interaction format: {interaction_data} (Error: {e})")
                        
                except Exception as e:
                    print(f"💥 Error processing interaction: {e}")

    except KeyboardInterrupt:
        print("\nController interrupted")
    
    finally:
        # Cleanup
        print("🧹 Cleaning up controller...")
        try:
            interactions.close()
            control.close()
            heartbeats.close()
            api_socket.close()
            context.term()
            print("Controller cleanup complete")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")


if __name__ == "__main__":
    main()
