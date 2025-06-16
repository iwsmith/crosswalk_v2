import threading
from typing import Optional

import zmq
from pydantic import BaseModel

from xwalk2.models import TimerExpired, PlayScene, ResetCommand, EndScene
from xwalk2.util import SubscribeInteractComponent


class SceneTimer(SubscribeInteractComponent):
    """Scene timer with audio-duration detection and command handling"""

    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address="tcp://127.0.0.1:5556",
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        super().__init__(component_name, host_name, interact_address, subscribe_address)
        self.current_timer: Optional[threading.Timer] = None
        self.timer_lock = threading.Lock()
        self.timer_id_counter = 0
        self.last_timer_id = None

    def process_message(self, message: BaseModel):
        if isinstance(message, PlayScene):
            print(f"🎬 Play scene command - using sequence durations")
            self.start_scene_timer(message, self.interact_socket)

        elif isinstance(message, ResetCommand):
            self.stop_timer()
        
        elif isinstance(message, EndScene):
            self.stop_timer()

    def start_scene_timer(self, play_cmd: PlayScene, interaction_socket: zmq.Socket):
        """Start timer for scene duration"""
        # Keep this buffer around just in case things need tweaking
        base_duration = play_cmd.total_duration
        buffer_duration = base_duration + 0.1

        with self.timer_lock:
            # Cancel any existing timer
            if self.current_timer and self.current_timer.is_alive():
                self.current_timer.cancel()

            # Generate timer ID
            self.timer_id_counter += 1
            timer_id = f"scene_timer_{self.timer_id_counter}"
            self.last_timer_id = timer_id

            # Start new timer with buffer duration
            def timer_expired():
                print(f"Scene timer expired after {base_duration:.2f}s")
                timer_event = TimerExpired(timer_id=timer_id, duration=base_duration)  # Use original duration in event
                try:
                    interaction_socket.send_string(timer_event.model_dump_json())
                except Exception as e:
                    print(f"Error sending timer expired event: {e}")

            self.current_timer = threading.Timer(buffer_duration, timer_expired)
            self.current_timer.daemon = True
            self.current_timer.start()

            print(f"Scene timer started for {buffer_duration:.2f}s (ID: {timer_id})")

    def stop_timer(self):
        """Stop current timer"""
        with self.timer_lock:
            if self.current_timer and self.current_timer.is_alive():
                self.current_timer.cancel()
                print("Scene timer stopped")
                self.last_timer_id = None


if __name__ == "__main__":
    timer = SceneTimer("timer", "crosswalk-a")
    timer.run()
