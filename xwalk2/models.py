import json
from datetime import datetime
from typing import Dict, Literal, Optional, List, Union, Tuple

from pydantic import BaseModel, Field, model_validator, field_validator

# Models represent things we send over the wire for easy
# jsonification with pydantic.

WalkCategory = Literal['actions', 'actionsplus', 'airguitar', 'animals', 'fin', 'game', 'spoken-word', 'language', 'normal', 'normalish', 'silly', 'sleep']

WeightSchedule = Dict[WalkCategory | Literal["_"], int]

class WalkInfo(BaseModel):
    audio: Optional[str] = None
    ignore_reselection: bool = False

Walk = Dict[str, Union[None, WalkInfo]]

class MenuItem(BaseModel):
    start: datetime  # ISO format datetime string
    weights: str

    def __str__(self) -> str:
        return f"{self.start.strftime("%m/%d/%Y %H:%M:%S")} - {self.weights}"

    def __repr__(self) -> str:
        return f"MenuItem(start={self.start.isoformat()}, weights={self.weights})"

class ReselectionConfig(BaseModel):
    walk_cooldown: int = 10
    category_cooldown: int = 3
    cooldown_categories: List[WalkCategory] = Field(default_factory=list)

class Animations(BaseModel):
    intros: List[str]
    outros: List[str]
    walks: Dict[WalkCategory, Walk]
    weights: Dict[str, WeightSchedule]
    menu: List[MenuItem] = Field(
        default_factory=list,
        description="List of menu items with start times and weight schedules"
    )
    reselection: ReselectionConfig = Field(default_factory=ReselectionConfig)

    @model_validator(mode="after")
    def validate_menu_order(self) -> "Animations":
        """Ensure menu items are sorted by start time"""
        self.menu.sort(key=lambda item: item.start)
        return self

    def get_walk(self, walk_name: str) -> Optional[WalkInfo]:
        """Get walk information by name"""
        for category, walks in self.walks.items():
            if walk_name in walks:
                return walks[walk_name]
        return None


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

class APIQueueClear(BaseModel):
    """Request to queue a walk animation"""
    type: Literal["queue_clear"] = "queue_clear"

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
    walk_history: List[Tuple[datetime, str]] = Field(
        default_factory=list,
        description="History of walks with timestamps"
    )
    active_schedule: Optional[MenuItem] = None
    menu: List[MenuItem] = Field(
        default_factory=list,
        description="List of menu items with start times and weight schedules"
    )


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
    stop: str
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
    "queue_clear": APIQueueClear,
    "press_button": APIButtonPress,
    "timer_expired": APITimerExpired,
    "status": APIStatusRequest,
}

APIRequests = APIQueueWalk | APIButtonPress | APITimerExpired | APIStatusRequest | APIQueueClear

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
