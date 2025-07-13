import logging
from typing import Callable, List, Tuple

from pydantic import BaseModel
from transitions import Machine
from datetime import datetime

from xwalk2.animation_library import AnimationLibrary, WalkDefinition
from xwalk2.models import EndScene, PlayScene

logger = logging.getLogger(__name__)

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
        self.walk_queue: List[str] = []
        self.walk_history: List[Tuple[datetime, str]] = []

    def on_enter_walk(self):
        # We would choose a walk here
        queued_walk = self.walk_queue.pop(0) if self.walk_queue else None
        intro, walk, outro = self.animations.select_animation_sequence(walk=queued_walk)

        # Get durations for timing
        #total_duration = intro.duration + walk.duration + outro.duration
        total_duration =  walk.duration 

        # Create PlayScene
        play_command = PlayScene(
            intro=intro,
            walk=walk,
            outro=outro,
            stop=WalkDefinition(image="stop", audio="", duration=-1),  
            total_duration=total_duration,
        )
        self.send_message(play_command)
        self.walk_history.append((datetime.now(), walk.image))

    def on_enter_ready(self):
        self.send_message(EndScene())
