import json
from datetime import datetime
from typing import Dict, Literal, Optional, List, Union, Tuple

from pydantic import BaseModel, Field, model_validator, field_validator

# Models represent things we send over the wire for easy
# jsonification with pydantic.

WalkCategory = Literal["actions", "actionsplus", "airguitar", "animals", "animalsplus", "dance", "fin", "game", "karaoke", "language", "normal", "normalish", "silly", "sleep"]

WeightSchedule = Dict[WalkCategory | Literal["_"], int]

class WalkItem(BaseModel):
    audio: Optional[str] = None

class WalkInfo(BaseModel):
    category: WalkCategory
    ignore_reselection: bool = False
    audio: Optional[str] = None


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
    cooldown_categories: List[str] = Field(default_factory=list)


class Animations(BaseModel):
    intros: List[str]
    outros: List[str]
    walks: Dict[str, WalkInfo]
    weights: Dict[str, WeightSchedule]
    menu: List[MenuItem] = Field(
        default_factory=list,
        description="List of menu items with start times and weight schedules"
    )
    reselection: ReselectionConfig = Field(default_factory=ReselectionConfig)

    @model_validator(mode="before")
    @classmethod
    def restructure_walks(cls, data: any) -> any:
        """Restructures the 'walks' field from a nested to a flat structure."""
        if isinstance(data, dict) and "walks" in data and isinstance(data["walks"], dict):
            restructured_walks = {}
            for category, walks_dict in data["walks"].items():
                if not walks_dict:
                    continue
                for walk_name, walk_props in walks_dict.items():
                    props = walk_props or {}
                    props["category"] = category
                    restructured_walks[walk_name] = props
            data["walks"] = restructured_walks
        return data

    # This is silly. It translates the restructured config.yaml into a flat
    # dictionary of walk names to walk info which is kind of how we had the 
    # config.yaml before. Really, I should just use the new format. But we
    # are a little short on time.
    @field_validator("walks", mode="before")
    @classmethod
    def flatten_walks(cls, data: Dict) -> Dict:
        if not isinstance(data, dict):
            # This case can happen if the data is already processed
            return data

        flattened_walks = {}
        for category, walks in data.items():
            if not isinstance(walks, dict):
                continue
            for walk_name, walk_attrs in walks.items():
                audio = None
                if walk_attrs and "audio" in walk_attrs:
                    audio = walk_attrs["audio"]

                flattened_walks[walk_name] = {
                    "category": category,
                    "audio": audio,
                }
        return flattened_walks

    @model_validator(mode="after")
    def validate_menu_order(self) -> "Animations":
        """Ensure menu items are sorted by start time"""
        self.menu.sort(key=lambda item: item.start)
        return self


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
