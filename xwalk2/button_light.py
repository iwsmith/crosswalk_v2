import zmq
import json
from xwalk2.util import heatbeat
from xwalk2.models import PlayScene, ResetCommand, parse_message


def main():
    """Button lights function with command parsing"""
    print("Starting Button Lights...")
    
    # Socket to receive control commands
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5557")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    
    lights_on = True
    print(f"Button lights initialized. Lights: {'ON' if lights_on else 'OFF'}")
    
    # Start heartbeat
    heartbeat_thread = heatbeat("button_light", "crosswalk-a")
    
    try:
        while True:
            print(f"💡 Button lights status: {'ON' if lights_on else 'OFF'}")
            try:
                message = socket.recv_string()
                print(f"📨 Received command: {message}")
                
                try:
                    command_obj = parse_message(message)
                    
                    if isinstance(command_obj, PlayScene):
                        lights_on = False
                        print(f"🎬 Play scene command ({command_obj.intro} -> {command_obj.walk} -> {command_obj.outro}) - lights turned OFF")
                    
                    elif isinstance(command_obj, ResetCommand):
                        lights_on = True
                        print("🔄 Reset command - lights turned ON")
                    
                    else:
                        print(f"📋 Other command: {type(command_obj).__name__}")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"❓ Invalid command format: {message} (Error: {e})")
                
            except zmq.ZMQError as e:
                print(f"💥 ZMQ error: {e}")
                break
            except Exception as e:
                print(f"💥 Unexpected error: {e}")
    
    except KeyboardInterrupt:
        print("\n🛑 Shutting down button lights...")
    
    finally:
        # Cleanup
        if hasattr(heartbeat_thread, 'stop'):
            heartbeat_thread.stop()
        elif hasattr(heartbeat_thread, 'join'):
            heartbeat_thread.join()
        
        socket.close()
        context.term()
        print("Button lights shutdown complete")


if __name__ == "__main__":
    main()
