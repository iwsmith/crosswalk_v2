import zmq
import json
import time
import threading
from datetime import datetime
from xwalk2.util import heatbeat
from xwalk2.models import PlayScene, ResetCommand, EndScene, parse_message
from xwalk2.animation_library import AnimationLibrary


class SceneTimer:
    """Scene timer with audio-duration detection and command handling"""
    
    def __init__(self):
        self.animation_lib = None
        self.current_timer = None
        self.timer_lock = threading.Lock()
        self.timer_id_counter = 0
        
        # Initialize animation library for duration detection
        try:
            self.animation_lib = AnimationLibrary()
            print("✅ Animation library loaded for duration detection")
        except Exception as e:
            print(f"⚠️  Animation library not available: {e}")
            print("   Falling back to default 10s timing")
    
    def get_scene_duration(self, play_cmd: PlayScene) -> float:
        """Get duration from PlayScene"""
        duration = play_cmd.total_duration
        print(f"🎬 Using scene duration: {duration:.2f}s")
        return duration
    
    def start_scene_timer(self, play_cmd: PlayScene, interaction_socket: zmq.Socket):
        """Start timer for scene duration"""
        duration = self.get_scene_duration(play_cmd)
        
        with self.timer_lock:
            # Cancel any existing timer
            if self.current_timer and self.current_timer.is_alive():
                self.current_timer.cancel()
            
            # Generate timer ID
            self.timer_id_counter += 1
            timer_id = f"scene_timer_{self.timer_id_counter}"
            
            # Start new timer
            def timer_expired():
                print(f"⏰ Scene timer expired after {duration:.2f}s")
                timer_event = EndScene(
                    timer_id=timer_id,
                    duration=duration
                )
                interaction_socket.send_string(timer_event.model_dump_json())
            
            self.current_timer = threading.Timer(duration, timer_expired)
            self.current_timer.daemon = True
            self.current_timer.start()
            
            print(f"⏲️  Scene timer started for {duration:.2f}s (ID: {timer_id})")
    
    def stop_timer(self):
        """Stop current timer"""
        with self.timer_lock:
            if self.current_timer and self.current_timer.is_alive():
                self.current_timer.cancel()
                print("🛑 Scene timer stopped")


def main():
    """Timer main function with command parsing"""
    print("Starting Scene Timer...")
    
    # Initialize scene timer
    timer = SceneTimer()
    
    # Socket to receive control commands
    context = zmq.Context()
    control = context.socket(zmq.SUB)
    control.connect("tcp://127.0.0.1:5557")
    control.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
    
    # Socket to send interactions
    interaction = context.socket(zmq.PUB)
    interaction.connect("tcp://127.0.0.1:5556")
    
    # Start heartbeat
    heartbeat_thread = heatbeat("timer", "crosswalk-a")
    
    print("Scene timer ready. Listening for scene commands...")
    
    try:
        while True:
            try:
                command = control.recv_string()
                print(f"📨 Received command: {command}")
                
                try:
                    command_obj = parse_message(command)
                    
                    if isinstance(command_obj, PlayScene):
                        print(f"🎬 Play scene command - using sequence durations")
                        timer.start_scene_timer(command_obj, interaction)
                    
                    elif isinstance(command_obj, ResetCommand):
                        print("🔄 Reset command - stopping timer")
                        timer.stop_timer()
                    
                    else:
                        print(f"📋 Other command: {type(command_obj).__name__}")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"❓ Invalid command format: {command} (Error: {e})")
                    
            except zmq.ZMQError as e:
                print(f"💥 ZMQ error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down scene timer...")
    
    finally:
        # Cleanup
        timer.stop_timer()
        
        if hasattr(heartbeat_thread, 'stop'):
            heartbeat_thread.stop()
        elif hasattr(heartbeat_thread, 'join'):
            heartbeat_thread.join()
        
        control.close()
        interaction.close()
        context.term()
        print("✅ Scene timer shutdown complete")


if __name__ == "__main__":
    main()
