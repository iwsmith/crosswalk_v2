from pydantic import BaseModel
from datetime import datetime

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
