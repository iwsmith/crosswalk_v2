import json
from datetime import datetime
from typing import Dict, Literal, Optional, List, Union

from pydantic import BaseModel, Field

# Models represent things we send over the wire for easy
# jsonification with pydantic.

WalkCategory = Literal["normalish"]

WeightSchedule = Dict[WalkCategory | Literal["_"], int]

class WalkInfo(BaseModel):
    category: WalkCategory 

class Animations(BaseModel):
    intros: List[str]
    outros: List[str]
    walks: Dict[str, WalkInfo]
    weights: Dict[str, WeightSchedule]


class Heatbeat(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    host: str
    component: str
    sent_at: datetime
    initial: bool


class ButtonPress(BaseModel):
    type: Literal["button_press"] = "button_press"
    host: str
    component: str
    press_duration: int
    sent_at: datetime


class APIQueueWalk(BaseModel):
    """Request to queue a walk animation"""
    type: Literal["queue_walk"] = "queue_walk"
    walk: str  # Name of the walk animation to queue

class APIButtonPress(BaseModel):
    """Request to queue a walk animation"""
    type: Literal["press_button"] = "press_button"

class APITimerExpired(BaseModel):
    """Event sent when a timer expires"""
    type: Literal["timer_expired"] = "timer_expired"

class APIStatusRequest(BaseModel):
    """Request to get the current status of the system"""
    type: Literal["status"] = "status"


class APIResponse(BaseModel):
    message: str
    success: bool
    playing: bool
    components: Dict[str, datetime]
    timestamp: datetime
    state: str
    animations: Animations
    walk_queue: List[str] = Field(default_factory=list, description="List of queued walk animations")


class ResetCommand(BaseModel):
    """Command to reset all components to idle state"""

    type: Literal["reset"] = "reset"


class CurrentState(BaseModel):
    """Current FSM state notification"""

    type: Literal["current_state"] = "current_state"
    state: Literal["walk", "ready"]


class PlayScene(BaseModel):
    """Command to play an animation sequence"""

    type: Literal["play_scene"] = "play_scene"
    intro: str
    walk: str
    outro: str
    intro_duration: float
    walk_duration: float
    outro_duration: float
    total_duration: float


class EndScene(BaseModel):
    """Event sent when a scene timer expires"""

    type: Literal["end_scene"] = "end_scene"


class TimerExpired(BaseModel):
    type: Literal["timer_expired"] = "timer_expired"
    timer_id: str
    duration: float


message_registry = {
    "button_press": ButtonPress,
    "heartbeat": Heatbeat,
    "play_scene": PlayScene,
    "end_scene": EndScene,
    "current_state": CurrentState,
    "reset": ResetCommand,
    "timer_expired": TimerExpired,
}

api_registry = {
    "queue_walk": APIQueueWalk,
    "press_button": APIButtonPress,
    "timer_expired": APITimerExpired,
    "status": APIStatusRequest,
}

APIRequests = APIQueueWalk | APIButtonPress | APITimerExpired | APIStatusRequest

def parse_api(request: str) -> BaseModel:
    data = json.loads(request)
    msg_type = data.get("type")
    model_cls = api_registry.get(msg_type)
    if model_cls is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    return model_cls(**data)


def parse_message(message_str: str) -> BaseModel:
    """Parse message string into appropriate model"""
    data = json.loads(message_str)
    msg_type = data.get("type")
    model_cls = message_registry.get(msg_type)
    if model_cls is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    return model_cls(**data)
