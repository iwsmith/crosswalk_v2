import json
from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel

# Models represent things we send over the wire for easy
# jsonification with pydantic.


class Heatbeat(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    host: str
    component: str
    sent_at: datetime


class ButtonPress(BaseModel):
    type: Literal["button_press"] = "button_press"
    host: str
    component: str
    press_duration: int
    sent_at: datetime


class APIRequest(BaseModel):
    request_type: Literal["status", "action"]
    action: Optional[str] = None  # Only used for action requests


class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    # Status response fields (only populated for status requests)
    playing: Optional[bool] = None
    components: Optional[Dict[str, datetime]] = None
    timestamp: Optional[datetime] = None


message_registry = {"button_press": ButtonPress, "heartbeat": Heatbeat}


def parse_message(message_str: str) -> BaseModel:
    data = json.loads(message_str)
    msg_type = data.get("type")
    model_cls = message_registry.get(msg_type)
    if model_cls is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    return model_cls(**data)
