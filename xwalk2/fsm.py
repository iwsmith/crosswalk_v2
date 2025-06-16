from typing import Callable

from pydantic import BaseModel
from transitions import Machine

from xwalk2.animation_library import AnimationLibrary
from xwalk2.models import EndScene, PlayScene


class Controller:
    states = ["ready", "walk"]

    def __init__(self, send_message_fn: Callable[[BaseModel], None]):
        self.machine = Machine(
            model=self,
            states=Controller.states,
            initial="ready",
            ignore_invalid_triggers=True,
        )
        self.machine.add_transition("button_press", source="ready", dest="walk")
        self.machine.add_transition("timer_expired", source="walk", dest="ready")
        self.machine.add_transition("reset", source="*", dest="ready")
        self.animations = AnimationLibrary()
        self.send_message = send_message_fn

    def on_enter_walk(self):
        # We would choose a walk here
        intro, walk, outro = self.animations.select_animation_sequence()

        # Get durations for timing
        intro_duration, walk_duration, outro_duration = (
            self.animations.get_sequence_durations(intro, walk, outro)
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
            total_duration=total_duration,
        )
        self.send_message(play_command)

    def on_enter_ready(self):
        self.send_message(EndScene())
