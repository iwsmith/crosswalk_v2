from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional

# Models represent things we send over the wire for easy
# jsonification with pydantic.

class Heatbeat(BaseModel):
  host: str
  component: str
  sent_at: datetime

class ButtonPress(BaseModel):
  host: str
  component: str
  press_duration: int
  sent_at: datetime

class APIRequest(BaseModel):
  request_id: str
  request_type: str  # "status" or "action"
  action: Optional[str] = None  # Only used for action requests

class APIResponse(BaseModel):
  request_id: str
  success: bool
  message: Optional[str] = None
  # Status response fields (only populated for status requests)
  playing: Optional[bool] = None
  components: Optional[Dict[str, datetime]] = None
  timestamp: Optional[datetime] = None
