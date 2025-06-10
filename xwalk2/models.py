from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional, Literal

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
  request_type: Literal["status", "action"]  
  action: Optional[str] = None  # Only used for action requests

class APIResponse(BaseModel):
  success: bool
  message: Optional[str] = None
  # Status response fields (only populated for status requests)
  playing: Optional[bool] = None
  components: Optional[Dict[str, datetime]] = None
  timestamp: Optional[datetime] = None
